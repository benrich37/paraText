# Development log

Newest entries first. Record decisions and their reasons, not only what changed.

## 2026-11-04 (evening): linked files in questions, descriptions, reciprocal links (issues 5-7)

- Linked files are sent with whole-paper questions as `<linked_file>` blocks after the paper, not merged into
  it, so the model can name the source. Budget: 300k chars for the paper plus 200k shared by links, in link
  order; a link that gets no room is listed as omitted so the model knows it exists.
- Descriptions exist so the model knows *when* to consult a file, as the tester asked: on linking, the current
  provider is asked for one or two sentences from a sample (PDF title + first pages, head of a text file, a
  folder listing); the reader can overwrite it ("Describe…", stored with `description_by = "user"`). The
  description is also part of the question-cache fingerprint, so changing it invalidates earlier answers.
- Reciprocal PDF links are stored explicitly under the linked PDF's hash (computed at link time) rather than
  derived at read time, so they survive renames of either file. Data files and folders have no link list of
  their own, so those links stay one-way.
- The back button was retracted by the tester (new windows keep the original open), so it was not built.
- Verified with the fake provider only; no live question with a real SI has been run from this session.

## 2026-11-04 (later still): linked files (reported issue 4)

- Links are user data, so they live in the config directory (`links.json`), not the cache, and are keyed by the
  PDF's SHA-256 (already computed for the cache name) so renaming or moving the paper keeps them. One file for
  all papers keeps it easy to inspect and back up.
- Three buttons instead of two: QFileDialog cannot select files and directories in one native dialog, so
  "Link folder…" is separate from "Link data…" (any files, multi-select). All start in the active PDF's folder.
- Linked PDFs open in a *second* `ReaderWindow` rather than replacing the paper, since SI is read alongside it.
  Child windows share the config, provider name and profile but have their own engine and cache file.
- Not done: feeding linked SI text into whole-paper questions (roadmap item 19).

## 2026-11-04 (later): first three reported issues

- **Claude Code model/effort/Fable.** Checked live: `claude -p --model fable --effort low --output-format json`
  works on Claude Code 2.1.318 and `modelUsage` names the resolved id (`fable` → `claude-fable-5-1`, `opus` →
  `claude-opus-5-5`; a `claude-haiku-5-5` entry also appears, presumably a helper task, so the probe picks the id
  that contains the alias). There is no model-listing command, so "Check models" is a probe: four one-word
  prompts. `CommandProvider` gained `effort`/`effort_args` mirroring `model`/`model_args`; the full command is
  the cache key, so model and effort changes start a fresh cache as before.
- **Hover popup.** `QToolTip` was dropped for a custom window rather than fought with: its hiding rules (timeout
  by text length, hide on leaving the rect, hide on any mouse move for a tooltip without a rect) are not
  configurable enough for "stay until dismissed". The popup is dismissed by a click/wheel/key in the viewport
  (event filter), Escape, another term, or deactivation; leaving the term keeps it.
- **"Fe" vs "FE".** Diagnosed as a matching bug first: keys were lowercased, so "FE" (Faradaic efficiency,
  found offline or by the model) and "Fe" collided and the FE entry was underlined at every "Fe". Short
  capitalized single tokens are now case-sensitive keys. This changed the keys of acronym entries ("dft" →
  "DFT"), so the cache is re-keyed on load instead of bumping `CACHE_VERSION` (which would discard glossaries).
  Provider metadata is stored per entry even though a cache file is already per provider, because proofreading
  can be done by a different model than the one that wrote an entry (it is stored in the proofreader's file).
- **Proofread** is per page with the page text as context, since that is what disambiguates "Fe". An entry that
  occurs on several pages is checked on each (the counts reflect that). Acronym entries are never changed.

## 2026-11-04: "Log an issue" box

- A single-line box at the bottom of the side panel; Enter appends an entry to `notes/ReportedIssues.md`
  (`issues.py`). The file is found by walking up from the package to `pyproject.toml`, which only exists for an
  editable install (the development setup, and what the macOS bundle runs); otherwise the file goes to the config
  dir, and `$PARATEXT_ISSUES` overrides both. The file was created with its header so CLAUDE.md can point at it.
- The verbatim note is the record; the AI write-up (title, category, 2-4 sentence description, via a JSON schema
  on the *current* provider) is a convenience and must never block logging: provider errors go into the entry as
  "No AI write-up: ...", and the status bar says so. Context captured: paper, current page, provider cache key
  (name, model, effort), audience and the side-panel title, so a quality complaint can be reproduced.
- The write-up runs on the global `QThreadPool` rather than the engine's executor because the box also works
  with no document (and hence no engine) open.
- Tests use `testing.FakeIssueProvider`; `FakeProvider` cannot answer a schema prompt that has no `<page>`.

## 2026-11-03 (later): "Ask about the paper as a whole"

- A question box under the side panel (`ReaderWindow.ask_question`), `ContextEngine.ask`/`ask_job`, and
  `paratext ask`. The prompt (`prompts.question_prompt`) carries the **entire paper** as `<page number="N">`
  blocks (`PdfDocument.full_text`), not the per-page context the glossary uses, because questions like "does the
  paper prove X?" need the results and discussion, wherever they are. The cap is 300k characters (about 75k
  tokens) cut at a page boundary; the prompt then says that only the first pages are included. No provider is
  known to reject that size; subscription CLIs get it on stdin as before.
- The prompt asks the model to say *where* the paper supports a claim and to separate what the paper shows from
  what it assumes or cites, since "does it prove X" is exactly the question models are tempted to answer too
  generously. `PROMPT_VERSION` was not bumped: no existing prompt changed, and question answers live under their
  own cache key.
- Answers are stored as a `questions` list in the same cache file (backwards compatible: older files just lack
  the key), so the per-paper history survives restarts; the panel appends up to five earlier Q&A pairs below the
  current answer. A one-shot question has no memory of earlier answers; that is a roadmap item.
- Verified with tests only (engine, CLI, GUI with `FakeProvider`); no live call, same as everything else.

## 2026-11-03: macOS app bundle ("Open With" for PDFs)

- `paratext install-app` (`macapp.py`) writes `~/Applications/paraText.app`. Chosen over py2app/PyInstaller
  because the user just wants Finder to open PDFs in the reader from this repo: the bundle's executable is a
  shell script that `exec`s the installer's `sys.executable` (the project venv) with `-m paratext read`. No
  copying of Python or Qt, nothing to rebuild after a code change; rerun only if the venv moves.
- **Finder passes the file as an Apple Event, not as argv.** Verified: `open -a paraText.app x.pdf` starts
  `python -m paratext read` with no arguments and Qt delivers a `QFileOpenEvent`. `FileOpenHandler` (event filter
  on the `QApplication`, installed in `run()`) opens it; a second `open` while running opens into the same window.
  `exec` keeps the PID, so Launch Services delivers the event to the Python process and the Dock shows "paraText"
  with the bundle path (`lsappinfo` confirmed). The LS dump flags the bundle `shell-script` and `launch-disabled`,
  which did not stop `open -a` or the document claim (`PDF document`, rank Alternate).
- The launcher bakes in the installing shell's `PATH` (Finder-launched apps get the minimal system one, which would
  break the `claude`/`codex`/`gemini` subscription providers) and appends stdout/stderr to
  `~/Library/Logs/paraText.log`; `PARATEXT_LOG=INFO` turns on `logging.basicConfig` in `run()`.
- Icon: a QPainter drawing (page lines plus an underlined "para") turned into `.icns` by `sips` + `iconutil`;
  skipped silently off macOS. Not code-signed; it is a local, per-user install, and Gatekeeper does not object to
  an unsigned shell-script bundle created locally.
- Not verified: the window title / menu-bar name as seen on screen (AppleScript needs assistive access), and
  whether the "launch-disabled" flag matters for drag-and-drop onto the Dock icon.

## 2026-11-01 (later): model/effort per provider, reader profile

- The setup dialog's rows and choices now come from `providers.provider_capabilities(settings)`: Anthropic has
  model + effort (`low`…`max`), OpenAI-compatible has model (+ Fetch models) and an optional effort sent as
  `reasoning_effort` (blank by default; local servers may reject it), subscription CLIs have a model that becomes
  the tool's model flag via the preset's `model_args` and no effort (those tools don't expose one on the command
  line, as far as I know; unverified). Help text under each field explains the trade-off. Model and effort are in
  `cache_key`, so changing them regenerates explanations.
- Research on "memory of what the user knows" is written up in `notes/user_profile_design.md` (learner models and
  open learner models from tutoring systems; extract/reconcile memory layers like Mem0 and Letta; why the memory
  stays local and user-approved here). v1 implements the declared profile: `profile.UserProfile` (TOML, local),
  the "About you…" dialog, the paragraph appended to the system prompt, `known` concepts excluded from the
  glossary, and the profile fingerprint in the cache key. `PROMPT_VERSION` bumped to 2. The inferred path (from
  highlight-and-ask questions) is designed, not built: roadmap items 15–16.
- Verification: offscreen tests for every new path (effort/model plumbing, capability-driven rows, profile
  round-trip, prompts, dialog, reader wiring) and rendered screenshots of the three dialogs. Still no live AI
  call, still unseen on a real screen.

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
