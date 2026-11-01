# Development log

Newest entries first. Record decisions and their reasons, not only what changed.

## 2026-11-01: Qt reader, setup dialog, tooltip colours

The user asked for three things: fix the tooltip colours (white text on tan was unreadable), make provider setup
user-friendly (ideally entirely in the GUI), and reconsider tkinter for the reader, treating the original code as a
legacy proof of concept.

### Framework decision: PySide6 (Qt 6)

What the reader needs: crisp page rendering on HiDPI, continuous scrolling and zoom, overlays positioned at word
boxes, hover hit-testing with tooltips that stay on screen, text selection, background threads with safe GUI
updates, a forms-style settings dialog, and tests that run in CI without a display.

| Option | Verdict |
|---|---|
| **PySide6** (Qt Widgets) | Chosen. `QGraphicsView` gives zoom/scroll/overlays with no manual geometry; `QToolTip` handles rich text and screen edges; signals deliver worker-thread results on the GUI thread; `QT_QPA_PLATFORM=offscreen` runs GUI tests headless (works on this Mac and in CI); pytest-qt exists; LGPL; wheels for all three OSes. Cost: a ~350 MB install (`PySide6-Essentials`). |
| PyQt6 | Same toolkit, GPL/commercial licence. No reason to prefer it. |
| wxPython | Native widgets, mature, but no equivalent of QGraphicsView for a zoomable canvas with items, and no offscreen test backend. |
| Flet (Flutter) | Good for cross-platform forms; no custom-drawn, hit-testable document canvas. Web-ish rendering. |
| Dear PyGui | GPU immediate mode; custom-drawn widgets, weak text rendering, no native look, no PDF. |
| Kivy / Toga | Touch-first / immature widget coverage. |
| Web front-end (PDF.js + NiceGUI or pywebview) | Best PDF text layer, but hit-testing and overlays need JavaScript; a second language. Kept as a roadmap option, not needed for desktop. |
| tkinter (status quo) | Blurry on Retina, manual hit-testing and tooltip placement, no dark-mode-safe colours, one page at a time. |

Sources checked: PyPI versions (PySide6 6.12.0, pytest-qt 4.5.0), the Unite.AI framework guide (secondary),
and Qt forum threads on offscreen testing. PySide6 ships QtPdf as well, but PyMuPDF already gives word boxes,
so the reader keeps PyMuPDF for rendering and text.

### What changed

- `reader/` is new: `pageview.py` (DocumentView, PageItem, PixmapCache, render job), `app.py` (ReaderWindow),
  `setup.py` (SetupDialog). The tkinter reader is gone (git history has it). The legacy `widget.ParaText` stays.
- Tooltip colours: explicit `color: #1b1b1b; background: #fff9db` in `TOOLTIP_STYLE`, applied app-wide. The old
  tkinter tooltip set only the background, so macOS dark mode supplied white text.
- Setup dialog: options grouped by how the user pays (subscription CLI / API key / local), each with a readiness
  check (`preset_status`: CLI on PATH, key present, model chosen), per-kind form rows, "Fetch models"
  (`list_models` → `GET /models`), "Send a test prompt", and "Save and use" → `Config.save()` (0600 because
  it may hold a key). Also reachable as `paratext setup`. The reader shows an info bar with a "Set up AI…" button
  when no provider is ready. Provider and audience changes in the toolbar are saved to the config too.
- `pdf.PdfDocument` got a lock (PyMuPDF is not thread-safe; the render thread and engine workers now share a
  document) and a raw-RGB `render` for Qt.
- Continuous scrolling, HiDPI-correct rendering, zoom with Ctrl/⌘+wheel and "Fit width", "Explain whole paper",
  and single-click word selection came with the rewrite.

### Verification

- 143 tests pass offscreen on macOS in ~7 s, including hover → tooltip text, click → panel, drag → selection →
  explanation, paging, zoom → background render, offline mode, broken config, and the dialog's save/test/fetch
  flows (with monkeypatched network and CLI lookups).
- **Still not seen on a screen.** No human has looked at the Qt window or dialog yet; see roadmap item 0.
- **Still no live AI call.** Same situation as before: no keys or CLIs on this machine.
- CI on Linux needs `libegl1 libopengl0 libgl1 libxkbcommon0` for PySide6 even offscreen; the workflow installs
  them. Unverified until the workflow runs.

## 2026-10-31: modernization (branch `modernize`)

The user asked for three things in order:
1. clean up the 2022 repo (bugs, mistakes);
2. make the tests match the format of their other repos;
3. build a scientific-paper PDF reader with AI hover explanations that works with the user's *own* AI
   subscription from any vendor.

All work is uncommitted on `modernize` unless the git log says otherwise. The user had not asked for commits.

### 1. Cleanup

The `classes/`, `libs/`, `utils/` and `test/` directories became the `src/paratext/` package. Files were moved with
`git mv`, so history follows them:
- `widget.py` (was `classes/paraText.py`)
- `textutils.py` (was `libs/utils.py`)
- `bst.py` (was `libs/BSTTree.py`)
- `testing.py` (was `libs/event_gen.py`)

`environment.yml` and the machine-specific `test/reference/environment.yml` were removed, and the `sys.path` hacks
were replaced by an installable package.

Bugs fixed (each has a regression test):
- `make_darker` produced invalid 5-digit colors (`#91a2b`) whenever a channel was below 0x20, and crashed on
  lowercase hex (`short_hex_to_dec` only knew uppercase). The old test asserted the buggy output.
- `str_not` returned a bool, although its callers treat the result as a 'True'/'False' string.
- `del_fn(None)` and `clear_widget_holder()` on an empty holder crashed.
- `return_matches` produced overlapping matches and used column-only index arithmetic.
- The `insert_at_end` trick, used to keep tags while replacing text, lost the tag on 1-character spans and broke on
  multi-line spans. It was replaced by `replace_tagged_text`, which inserts with the old tags and then deletes.
- `replace_text` always left the widget `DISABLED`. It now restores the prior state.
- `parse_child_rep_tag` / `gen_changing_typebox_get_to_fro` called `sys.exit(1)`. They now raise `ValueError`.
- `get_synced_tags` crashed on `_ISO_` tags.
- Right-click was bound to both Button-2 and Button-3, so middle-click opened menus on Linux and Windows. It is now
  platform-aware.
- Popups were placed at event coords relative to the Text widget but inside its master, so the widget's padding
  offset them.
- The sync-indicator `after(500, clear_widget_holder)` could destroy an options menu opened during those 500 ms. It now
  destroys only its own frame.
- A second right-click left the first popup behind.
- `add_tag_idcs` silently ignored an odd-length index list.
- The BST demo read `../test/reference/words2.txt` relative to the cwd. `unittestsBST.py` had a hardcoded
  `/home/jovyan` path and no `test_`-prefixed methods, so it never ran.
- README fixes: it referred to a nonexistent `demos.py` and an IDE run-config screenshot.

### 2. Test format

The user's own repos (crawfish, cvtypecorr, JDFTxFreeNrg, id_unusable) share these conventions:
- `pyproject.toml` (setuptools, `dynamic` version from `__version__`)
- `src/` layout
- plain pytest functions in `tests/test_*.py` with a `conftest.py`
- `python -m pytest`
- pre-commit with check-yaml / end-of-file-fixer / trailing-whitespace
- ruff at line length 120, py310

None of those repos has GitHub CI. paraText already had a workflow, so it was kept and modernized (pre-commit, plus
pytest on a 3-OS × 2-Python matrix with `pyvista/setup-headless-display-action`). The ruff pre-commit hook is enabled
here, unlike in crawfish. The unittest classes were converted to fixtures (`tk_root`, `env`).

### 3. PDF reader

Key decisions:
- **tkinter + PyMuPDF**, not a web app with PDF.js. It keeps the project pure Python, matching the user's skills and
  the repo's tkinter roots, and the headless-Tk test approach still works. `engine.py` is GUI-independent, so a
  web front-end can be added later (see roadmap). PyMuPDF is AGPL; this is noted in the README.
- **"Link the user's subscription"**: consumer chat plans don't include API keys. The supported routes are therefore:
  - vendor CLIs that sign in with the subscription (`claude -p`, `codex exec -`, `gemini`), run as subprocesses;
  - pay-per-use API keys;
  - local servers.

  OpenAI-compatible HTTP covers most vendors with the stdlib alone. Anthropic goes through the official SDK, per the
  `claude-api` skill, which forbids hand-rolled HTTP or OpenAI-compatible shims for Claude.
- **Anthropic defaults** (from the `claude-api` skill, model table cached 2026-10-06):
  - model `claude-opus-5-5` (the skill says to default to it and never downgrade on the user's behalf);
  - `effort="low"`, set explicitly because the Opus 5.5 default is `medium`. Glossary extraction is a simple task.
    The user can change it.
  - JSON via `output_config.format`;
  - `fallbacks="default"` with beta `server-side-fallback-2026-07-01` on models that support it (opt-in by default
    per the skill; turn it off with `refusal_fallback = false`);
  - no `temperature` (rejected on current models), and refusals checked before reading content.
- **Per-page glossary requests** that pass in the terms already known, plus offline acronym detection, so the reader
  is useful with no provider at all. Opening a page prefetches the next one. A page is not reprocessed once done.
- **Explanation honesty**: tooltips and the panel show "AI-generated by <provider>; may contain mistakes" or "Defined
  in the paper", and the system prompt forbids inventing results or numbers.

Verification performed:
- 124 tests pass locally (macOS, Python 3.12, Tk 8.6) in about 5 s, and pre-commit passes.
- Offline engine on a real 9-page paper (`~/Downloads/mazánek-et-al-2019-...pdf`): 10 acronyms, all with correct
  long forms; load time 0.06 s. This run revealed the ligature bug (PyMuPDF keeps "ﬁ"/"ﬀ"), now fixed in two places
  (extraction flags and NFKC in `normalize_token`).
- Underline alignment was checked by drawing the reader's computed underline geometry onto the rendered page; it is
  correct, including a term wrapped across lines.

**Not** verified:
- **No live AI call has been made.** The machine has no API keys and no `claude`/`codex`/`gemini`/`ollama` CLI.
  Providers are tested against a local HTTP server, a stubbed SDK client and fake CLI scripts.
- **The GUI was never seen on screen.** `screencapture` failed, probably for lack of Screen Recording permission.
  The GUI tests exercise hover, click, select and paging through synthetic events only.
- Observed once: the first full `pytest` run took over 180 s to *exit* after reporting "123 passed in 6s", and a later
  run took 27 s. It was not reproducible afterwards (5–6 s, repeatedly). It may have been macOS scanning the freshly
  installed native libraries. If it comes back, dump threads in `pytest_unconfigure`; only `MainThread` was alive at
  exit when checked.
