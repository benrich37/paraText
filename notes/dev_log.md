# Development log

Newest entries first. Record decisions and their reasons, not only what changed.

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
