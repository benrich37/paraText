"""Command line: ``paratext read|glossary|explain|ask|links|setup|providers|config|install-app``."""

from __future__ import annotations

import argparse
import json
import sys

from paratext.ai.providers import PRESETS, ProviderError, make_provider, preset_status
from paratext.config import Config, default_config_path, write_template
from paratext.engine import ContextEngine, ImmediateExecutor
from paratext.glossary import find_spans


def parse_pages(spec: str | None, page_count: int) -> list[int]:
    """Parse '1,3-5' (1-based, inclusive) into sorted 0-based page indices."""
    if not spec:
        return list(range(page_count))
    pages = set()
    for part in spec.split(","):
        part = part.strip()
        if "-" in part:
            lo, hi = part.split("-", 1)
            pages.update(range(int(lo) - 1, int(hi)))
        elif part:
            pages.add(int(part) - 1)
    bad = [p + 1 for p in pages if not 0 <= p < page_count]
    if bad:
        raise SystemExit(f"Page(s) out of range 1-{page_count}: {bad}")
    return sorted(pages)


def _engine(args, config: Config) -> ContextEngine:
    from paratext.links import LinkStore
    from paratext.pdf import PdfDocument
    from paratext.profile import UserProfile

    provider = config.make_provider(args.provider)
    audience = args.audience or config.audience
    return ContextEngine(
        PdfDocument(args.pdf),
        provider,
        config.cache_dir,
        audience,
        executor=ImmediateExecutor(),
        profile=UserProfile.load(),
        link_store=LinkStore(),
    )


def cmd_read(args, config: Config) -> int:
    from paratext.reader import run

    run(args.pdf, args.provider, args.config)
    return 0


def cmd_glossary(args, config: Config) -> int:
    engine = _engine(args, config)
    pages = parse_pages(args.pages, engine.doc.page_count)
    errors = 0
    if engine.provider is None:
        print("No AI provider configured; listing acronyms defined in the paper only.", file=sys.stderr)
    else:
        for page in pages:
            if engine.is_page_done(page):
                continue
            print(f"page {page + 1}/{engine.doc.page_count} …", file=sys.stderr)
            try:
                engine.page_job(page)
            except ProviderError as e:
                errors += 1
                print(f"  page {page + 1}: {e}", file=sys.stderr)
    entries = sorted(
        (e for e in engine.terms.values() if e.page is None or e.page in pages), key=lambda e: e.term.lower()
    )
    if args.json:
        print(json.dumps([e.to_dict() for e in entries], indent=1, ensure_ascii=False))
    else:
        for e in entries:
            print(f"{e.term}\n    {e.explanation}\n")
    return 1 if errors else 0


def cmd_explain(args, config: Config) -> int:
    engine = _engine(args, config)
    page = args.page - 1
    if not 0 <= page < engine.doc.page_count:
        raise SystemExit(f"--page must be between 1 and {engine.doc.page_count}")
    words = [w.text for w in engine.doc.words(page)]
    spans = find_spans(words, [args.phrase], engine.doc.line_ends(page))
    if spans:
        start, end = spans[0].start, spans[0].end
    else:
        start = end = 0
        print(f"note: {args.phrase!r} not found on page {args.page}; using the page start as context.", file=sys.stderr)
    text = engine.cached_explanation(args.phrase, page, args.detailed)
    if text is None:
        text = engine.explain_job(args.phrase, page, start, end, args.detailed)
    print(text)
    return 0


def cmd_ask(args, config: Config) -> int:
    engine = _engine(args, config)
    text = engine.cached_answer(args.question)
    if text is None:
        text = engine.ask_job(args.question)
    print(text)
    return 0


def cmd_links(args, config: Config) -> int:
    """List, add or remove files linked to a paper (SI PDFs, data, folders)."""
    from paratext.links import LinkStore
    from paratext.pdf import PdfDocument

    doc = PdfDocument(args.pdf)
    store = LinkStore()
    try:
        for path in args.add or []:
            link = store.add(doc.sha256, path, args.kind, doc_path=str(doc.path))
            print(f"linked {link.kind}: {link.path}")
        for path in args.remove or []:
            print(f"{'removed' if store.remove(doc.sha256, path) else 'not linked'}: {path}")
        if args.describe:
            path, text = args.describe
            print(f"{'described' if store.set_description(doc.sha256, path, text) else 'not linked'}: {path}")
        links = store.links(doc.sha256)
        if not links:
            print(f"no files linked to {doc.title} ({store.path})")
        for link in links:
            desc = f"\n      {link.description} ({link.description_by})" if link.description else ""
            print(f"  [{link.kind}] {link.path}{'' if link.exists else '  (missing)'}{desc}")
    finally:
        doc.close()
    return 0


def cmd_setup(args, config: Config) -> int:
    """Open just the AI setup dialog."""
    import sys as _sys

    from PySide6.QtWidgets import QApplication

    from paratext.reader.setup import SetupDialog

    _app = QApplication.instance() or QApplication(_sys.argv)  # must outlive the dialog
    dialog = SetupDialog(config, current=config.default_provider)
    if dialog.exec():
        print(f"saved {dialog.config.path}: default provider is {dialog.selected_name!r}")
        return 0
    print("cancelled")
    return 1


def cmd_providers(args, config: Config) -> int:
    print(f"config: {config.path}{'' if config.path and config.path.exists() else ' (not found)'}")
    print(f"default: {config.default_provider or 'none'}\n")
    status = 0
    for name in config.provider_names():
        settings = config.providers.get(name)
        try:
            provider = make_provider(name, settings) if settings is not None else make_provider(name)
            desc = provider.cache_key
        except ProviderError as e:
            provider, desc = None, f"not usable: {e}"
        origin = "config" if settings is not None else "preset"
        ready, readiness = preset_status(name, settings)
        line = f"  {name:<12} [{origin}] {'ready' if ready else 'not ready'}: {readiness}  ({desc})"
        if args.check and provider is not None and (settings is not None or name == config.default_provider):
            try:
                reply = provider.complete("You are a connectivity check.", "Reply with the single word OK.")
                line += f"  -> {reply.strip()[:40]!r}"
            except ProviderError as e:
                line += f"  -> FAILED: {e}"
                status = 1
        print(line)
    return status


def cmd_install_app(args, config: Config) -> int:
    """Write a macOS app bundle so Finder's "Open With" can open PDFs in the reader."""
    from paratext.macapp import build_app, register

    app = build_app(args.dest, icon=not args.no_icon)
    registered = register(app)
    print(f"wrote {app} (runs {sys.executable})")
    if registered:
        print("Registered with Launch Services: right-click a PDF > Open With > paraText. To make it the default,")
        print("use Get Info on a PDF > Open with > paraText > Change All.")
    else:
        print("note: Launch Services not found (not macOS?); the bundle was written but not registered.")
    return 0


def cmd_config(args, config: Config) -> int:
    if args.init:
        path = write_template(args.config)
        print(f"wrote {path}; edit default_provider and the provider you want to use.")
        return 0
    path = args.config or default_config_path()
    print(path)
    if config.path and config.path.exists():
        print(config.path.read_text())
    else:
        print("(no config file; run `paratext config --init`)")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="paratext", description=__doc__)
    parser.add_argument("--config", help="config file (default: $PARATEXT_CONFIG or ~/.config/paratext/config.toml)")
    sub = parser.add_subparsers(dest="command")

    def ai_args(p):
        p.add_argument("--provider", help=f"provider name from your config, a preset ({', '.join(PRESETS)}), or none")
        p.add_argument("--audience", help="who explanations are written for")

    p = sub.add_parser("read", help="open the PDF reader GUI")
    p.add_argument("pdf", nargs="?")
    ai_args(p)
    p.set_defaults(func=cmd_read)

    p = sub.add_parser("glossary", help="build (and cache) a glossary for a PDF and print it")
    p.add_argument("pdf")
    p.add_argument("--pages", help="pages to process, e.g. '1,3-5' (default: all)")
    p.add_argument("--json", action="store_true", help="print JSON")
    ai_args(p)
    p.set_defaults(func=cmd_glossary)

    p = sub.add_parser("explain", help="explain a phrase in the context of a page")
    p.add_argument("pdf")
    p.add_argument("phrase")
    p.add_argument("--page", type=int, default=1, help="1-based page the phrase is on")
    p.add_argument("--detailed", action="store_true")
    ai_args(p)
    p.set_defaults(func=cmd_explain)

    p = sub.add_parser("ask", help="ask a question about the paper as a whole")
    p.add_argument("pdf")
    p.add_argument("question")
    ai_args(p)
    p.set_defaults(func=cmd_ask)

    p = sub.add_parser("links", help="list or change the files linked to a paper (SI PDFs, data, folders)")
    p.add_argument("pdf")
    p.add_argument("--add", nargs="+", metavar="PATH", help="link these files or folders")
    p.add_argument("--kind", choices=["pdf", "data", "folder"], help="kind for --add (default: by file type)")
    p.add_argument("--remove", nargs="+", metavar="PATH", help="unlink these paths")
    p.add_argument("--describe", nargs=2, metavar=("PATH", "TEXT"), help="say what a linked file contains")
    p.set_defaults(func=cmd_links)

    p = sub.add_parser("setup", help="open the AI setup dialog")
    p.set_defaults(func=cmd_setup)

    p = sub.add_parser("providers", help="list configured providers and presets")
    p.add_argument("--check", action="store_true", help="send a tiny test prompt to configured providers")
    p.set_defaults(func=cmd_providers)

    p = sub.add_parser("install-app", help="macOS: write ~/Applications/paraText.app so Finder can open PDFs here")
    p.add_argument("--dest", help="where to write the bundle (default: ~/Applications/paraText.app)")
    p.add_argument("--no-icon", action="store_true", help="skip generating the app icon")
    p.set_defaults(func=cmd_install_app)

    p = sub.add_parser("config", help="show or create the config file")
    p.add_argument("--init", action="store_true", help="write a commented template config")
    p.set_defaults(func=cmd_config)
    return parser


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not args.command:
        args = parser.parse_args(["read", *(argv or sys.argv[1:])])
    config = Config.load(args.config)
    try:
        return args.func(args, config)
    except ProviderError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
