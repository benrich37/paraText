"""Continuous-scroll PDF page view on a QGraphicsView.

All geometry is in PDF points; zoom is the view transform.  Each page is a
``PageItem`` that paints a cached pixmap rendered (on a worker thread) at the
current effective scale, then its term underlines, hover box and selection.
"""

from __future__ import annotations

from collections import OrderedDict

from PySide6.QtCore import QObject, QPoint, QPointF, QRectF, QRunnable, Qt, QThreadPool, Signal
from PySide6.QtGui import QBrush, QColor, QImage, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QGraphicsItem, QGraphicsScene, QGraphicsView

from paratext.glossary import Span
from paratext.pdf import PdfDocument

PAGE_GAP = 12.0
MARGIN = 16.0
MAX_RENDER_SCALE = 4.0
UNDERLINE_COLORS = {"ai": "#d9480f", "acronym": "#1971c2", "user": "#2f9e44"}
SELECTION_COLOR = "#1c7ed6"
HOVER_COLOR = "#f08c00"


def line_rects(words, start: int, end: int) -> list[QRectF]:
    """One bounding box per text line covering words ``start..end`` (inclusive)."""
    rects: dict[tuple[int, int], list[float]] = {}
    for w in words[start : end + 1]:
        r = rects.setdefault((w.block, w.line), [w.x0, w.y0, w.x1, w.y1])
        r[0], r[1], r[2], r[3] = min(r[0], w.x0), min(r[1], w.y0), max(r[2], w.x1), max(r[3], w.y1)
    return [QRectF(x0, y0, x1 - x0, y1 - y0) for x0, y0, x1, y1 in rects.values()]


class TermSpan:
    """A glossary span on a page with its line boxes and underline colour."""

    __slots__ = ("span", "rects", "color")

    def __init__(self, span: Span, rects: list[QRectF], color: str):
        self.span, self.rects, self.color = span, rects, color

    def contains(self, pos) -> bool:
        return any(r.contains(pos) for r in self.rects)

    def bounding_rect(self) -> QRectF:
        rect = QRectF(self.rects[0])
        for r in self.rects[1:]:
            rect |= r
        return rect


class _RenderSignals(QObject):
    done = Signal(int, float, object)  # page, scale, QImage or None


class _RenderJob(QRunnable):
    def __init__(self, doc: PdfDocument, page: int, scale: float, signals: _RenderSignals):
        super().__init__()
        self.doc, self.page, self.scale, self.signals = doc, page, scale, signals

    def run(self) -> None:
        try:
            r = self.doc.render(self.page, self.scale)
            # copy() so the image owns its pixels after `samples` is released
            image = QImage(r.samples, r.width, r.height, r.stride, QImage.Format.Format_RGB888).copy()
        except Exception:  # the document may have been closed meanwhile
            image = None
        self.signals.done.emit(self.page, self.scale, image)


class PageItem(QGraphicsItem):
    def __init__(self, view: DocumentView, page: int, width: float, height: float):
        super().__init__()
        self.view = view
        self.page = page
        self.rect = QRectF(0, 0, width, height)
        self.spans: list[TermSpan] = []
        self.spans_version = -1
        self.hover_span: TermSpan | None = None
        self.selection: tuple[int, int] | None = None
        self._anchor: int | None = None
        self._dragged = False
        self.setAcceptHoverEvents(True)

    def boundingRect(self) -> QRectF:
        return self.rect

    # ------------------------------------------------------------------
    # painting
    # ------------------------------------------------------------------

    def paint(self, painter: QPainter, option, widget=None) -> None:
        dpr = widget.devicePixelRatioF() if widget is not None else 1.0
        scale = painter.worldTransform().m11() * dpr
        painter.fillRect(self.rect, Qt.GlobalColor.white)
        pixmap = self.view.cache.get(self.page, scale)
        if pixmap is not None:
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
            painter.drawPixmap(self.rect, pixmap, QRectF(pixmap.rect()))
        for term in self.spans:
            pen = QPen(QColor(term.color), 2)
            pen.setCosmetic(True)
            painter.setPen(pen)
            for r in term.rects:
                painter.drawLine(r.bottomLeft() + QPointF(0, 1), r.bottomRight() + QPointF(0, 1))
        if self.hover_span is not None:
            pen = QPen(QColor(HOVER_COLOR), 1)
            pen.setCosmetic(True)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            for r in self.hover_span.rects:
                painter.drawRect(r.adjusted(-1, -1, 1, 1))
        if self.selection is not None:
            pen = QPen(QColor(SELECTION_COLOR), 2)
            pen.setCosmetic(True)
            painter.setPen(pen)
            painter.setBrush(QBrush(QColor(28, 126, 214, 40)))
            for r in self.selection_rects():
                painter.drawRect(r.adjusted(-1, -1, 1, 1))

    def selection_rects(self) -> list[QRectF]:
        if self.selection is None:
            return []
        return line_rects(self.view.doc.words(self.page), *self.selection)

    # ------------------------------------------------------------------
    # hover and mouse
    # ------------------------------------------------------------------

    def span_at(self, pos) -> TermSpan | None:
        for term in self.spans:
            if term.contains(pos):
                return term
        return None

    def set_hover(self, term: TermSpan | None, screen_pos: QPoint | None = None) -> None:
        if term is self.hover_span:
            return
        self.hover_span = term
        self.update()
        self.view.termHovered.emit(self.page, term, screen_pos or QPoint())

    def hoverMoveEvent(self, event) -> None:
        self.set_hover(self.span_at(event.pos()), event.screenPos())

    def hoverLeaveEvent(self, event) -> None:
        self.set_hover(None)

    def mousePressEvent(self, event) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            event.ignore()
            return
        self.view.clear_selection()
        self._anchor = self.view.doc.word_at(self.page, event.pos().x(), event.pos().y())
        self._dragged = False
        event.accept()

    def mouseMoveEvent(self, event) -> None:
        if self._anchor is None:
            return
        word = self.view.doc.word_at(self.page, event.pos().x(), event.pos().y())
        if word is not None and (self.selection is None or word != self._sel_end):
            self._sel_end = word
            self._dragged = True
            self.selection = (min(self._anchor, word), max(self._anchor, word))
            self.update()

    def mouseReleaseEvent(self, event) -> None:
        anchor, self._anchor = self._anchor, None
        if not self._dragged:
            term = self.span_at(event.pos())
            if term is not None:
                self.view.termClicked.emit(self.page, term)
                return
            if anchor is None:
                return
            self.selection = (anchor, anchor)
            self.update()
        self.view.selectionChanged.emit(self.page, *self.selection)

    _sel_end: int | None = None


class PixmapCache:
    """LRU cache of rendered pages keyed by (page, scale); renders on demand."""

    def __init__(self, view: DocumentView, limit: int = 16):
        self.view = view
        self.limit = limit
        self.items: OrderedDict[tuple[int, float], QPixmap] = OrderedDict()
        self.pending: set[tuple[int, float]] = set()

    @staticmethod
    def key(scale: float) -> float:
        return round(min(max(scale, 0.1), MAX_RENDER_SCALE), 2)

    def get(self, page: int, scale: float) -> QPixmap | None:
        """Best available pixmap for a page; requests a render at ``scale`` if needed."""
        key = (page, self.key(scale))
        if key in self.items:
            self.items.move_to_end(key)
            return self.items[key]
        if key not in self.pending and self.view.doc is not None:
            self.pending.add(key)
            self.view.pool.start(_RenderJob(self.view.doc, page, key[1], self.view.render_signals))
        # fall back to any other scale (blurry until the right one arrives)
        candidates = [k for k in self.items if k[0] == page]
        if candidates:
            best = max(candidates, key=lambda k: k[1])
            return self.items[best]
        return None

    def put(self, page: int, scale: float, pixmap: QPixmap) -> None:
        key = (page, scale)
        self.pending.discard(key)
        self.items[key] = pixmap
        self.items.move_to_end(key)
        while len(self.items) > self.limit:
            self.items.popitem(last=False)

    def clear(self) -> None:
        self.items.clear()
        self.pending.clear()


class DocumentView(QGraphicsView):
    termHovered = Signal(int, object, QPoint)  # page, TermSpan or None, screen position
    termClicked = Signal(int, object)  # page, TermSpan
    selectionChanged = Signal(int, int, int)  # page, first word, last word
    currentPageChanged = Signal(int)
    visiblePagesChanged = Signal()
    zoomChanged = Signal(float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.doc: PdfDocument | None = None
        self.items: list[PageItem] = []
        self.cache = PixmapCache(self)
        self.pool = QThreadPool(self)
        self.pool.setMaxThreadCount(1)
        self.render_signals = _RenderSignals()
        self.render_signals.done.connect(self._render_done)
        self._current_page = 0
        #: "fit width" mode: re-fit on resize until the user zooms manually
        self.fit_mode = True
        self.setScene(QGraphicsScene(self))
        self.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.SmoothPixmapTransform)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
        self.setBackgroundBrush(QBrush(QColor("#868e96")))
        self.setMouseTracking(True)
        self.viewport().setMouseTracking(True)
        self.verticalScrollBar().valueChanged.connect(self._scrolled)

    # ------------------------------------------------------------------
    # document
    # ------------------------------------------------------------------

    def set_document(self, doc: PdfDocument | None) -> None:
        self.pool.clear()
        self.cache.clear()
        self.scene().clear()
        self.items = []
        self.doc = doc
        self._current_page = 0
        self.fit_mode = True
        if doc is None:
            self.setSceneRect(QRectF())
            return
        y = MARGIN
        max_w = 0.0
        for page in range(doc.page_count):
            w, h = doc.page_size(page)
            item = PageItem(self, page, w, h)
            item.setPos(0, y)
            self.scene().addItem(item)
            self.items.append(item)
            y += h + PAGE_GAP
            max_w = max(max_w, w)
        for item in self.items:  # centre narrower pages
            item.setPos((max_w - item.rect.width()) / 2, item.pos().y())
        self.setSceneRect(QRectF(-MARGIN, 0, max_w + 2 * MARGIN, y - PAGE_GAP + MARGIN))
        self.verticalScrollBar().setValue(0)

    def page_item(self, page: int) -> PageItem:
        return self.items[page]

    def _render_done(self, page: int, scale: float, image) -> None:
        if image is None or page >= len(self.items):
            self.cache.pending.discard((page, scale))
            return
        self.cache.put(page, scale, QPixmap.fromImage(image))
        self.items[page].update()

    # ------------------------------------------------------------------
    # pages and scrolling
    # ------------------------------------------------------------------

    def visible_pages(self) -> list[int]:
        if not self.items:
            return []
        area = self.mapToScene(self.viewport().rect()).boundingRect()
        return [item.page for item in self.items if item.sceneBoundingRect().intersects(area)]

    def current_page(self) -> int:
        return self._current_page

    def _scrolled(self, *_) -> None:
        if not self.items:
            return
        area = self.mapToScene(self.viewport().rect()).boundingRect()
        page, best = self._current_page, -1.0
        for item in self.items:  # the page with the largest visible area; ties go to the earlier page
            visible = item.sceneBoundingRect().intersected(area).height()
            if visible > best:
                page, best = item.page, visible
        self.visiblePagesChanged.emit()
        self._set_current(page)

    def _set_current(self, page: int) -> None:
        if page != self._current_page:
            self._current_page = page
            self.currentPageChanged.emit(page)

    def go_to(self, page: int) -> None:
        if not self.items:
            return
        page = max(0, min(page, len(self.items) - 1))
        top = self.items[page].sceneBoundingRect().top() - PAGE_GAP / 2
        self.verticalScrollBar().setValue(int(top * self.zoom_factor()))
        # explicit navigation wins even when the scroll range cannot move (all pages fit)
        self._set_current(page)

    # ------------------------------------------------------------------
    # zoom
    # ------------------------------------------------------------------

    def zoom_factor(self) -> float:
        return self.transform().m11()

    def set_zoom(self, factor: float) -> None:
        factor = max(0.25, min(factor, 6.0))
        self.resetTransform()
        self.scale(factor, factor)
        self.zoomChanged.emit(factor)
        self._scrolled()

    def zoom_by(self, ratio: float) -> None:
        self.fit_mode = False
        self.set_zoom(self.zoom_factor() * ratio)

    def fit_width(self) -> None:
        """Zoom so the widest page fills the view, and keep doing so on resize."""
        self.fit_mode = True
        if not self.items:
            return
        scene_w = self.sceneRect().width()
        avail = self.viewport().width() - 2
        if scene_w > 0 and avail > 0:
            self.set_zoom(avail / scene_w)

    def wheelEvent(self, event) -> None:
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            self.zoom_by(1.15 if event.angleDelta().y() > 0 else 1 / 1.15)
            event.accept()
        else:
            super().wheelEvent(event)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if self.fit_mode and self.items:
            self.fit_width()
        self._scrolled()

    # ------------------------------------------------------------------
    # selection helpers
    # ------------------------------------------------------------------

    def clear_selection(self) -> None:
        for item in self.items:
            if item.selection is not None:
                item.selection = None
                item.update()

    def selection(self) -> tuple[int, int, int] | None:
        """``(page, first word, last word)`` of the current selection, if any."""
        for item in self.items:
            if item.selection is not None:
                return (item.page, *item.selection)
        return None

    def term_viewport_rect(self, page: int, term: TermSpan):
        """Bounding box of a term span in viewport pixel coordinates."""
        item = self.items[page]
        return self.mapFromScene(item.mapToScene(term.bounding_rect())).boundingRect()
