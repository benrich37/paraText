# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

paraText is a tkinter prototype (CU Boulder "Software Engineering for Scientists" course project) that makes
technical text interactive. Words or phrases are underlined; right-clicking one opens a list of replacement
options, and shift-left-click toggles whether that instance is "synced" (replacing one replaces every synced
instance of the same pattern) or "unsynced" (only that instance changes). The only runtime dependency is the
standard library (tkinter); `environment.yml` is a conda env (`paraText`, Python 3.10, plus pycodestyle/numpy).

## Commands

```bash
# Run demos (the README says "demos.py", but the actual files are demoA.py and demoB.py)
python demos/demoA.py      # pattern-based tagging via add_tag_rep
python demos/demoB.py      # explicit index-based tagging via add_tag_idcs
python demos/BST_GUI.py    # standalone synonym-lookup GUI; must be run from demos/ (opens ../test/reference/words2.txt)

# paraText class tests (need a display, since they create a real Tk root). Can run from repo root
python test/unit/test_class_funcs.py
python -m unittest test.unit.test_class_funcs.TestClassFuncs.test_counter   # single test

# utils tests: MUST run from test/unit (the file does sys.path.append("../../libs/") relative to cwd)
cd test/unit && python -m unittest test_utils
cd test/unit && python -m unittest test_utils.TestUtils.test_make_darker   # single test

# Style (the CI job for it is currently commented out)
pycodestyle $(git ls-files "*.py")
```

CI (`.github/workflows/tests.yml`) runs on push/PR to `main`. It runs `test_utils` in the conda env and
`test_class_funcs.py` on macOS/Ubuntu/Windows with Python 3.9 and a headless display.

Non-functional test files: `test/functional/test_class_funcs.py` contains only imports. `utils/unittestsBST.py`
hardcodes `/home/jovyan/paraText/libs` and its methods lack the `test_` prefix, so unittest discovers nothing in it.

## Architecture

The core is a single class, `paraText` in `classes/paraText.py`, which subclasses `tk.Text`. All state lives in
**tk text tags whose names encode metadata**, plus two dicts on the instance.

### Tag naming convention (central to everything)
- `_ISO_<pattern>`: an "iso" tag, i.e. a single standalone replaceable span.
- `_REP_<pattern>`: a **parent** tag. It is never applied to text; it is only a dict key.
- `_REP_<id>_CNT_<True|False>_SNC_<pattern>`: a **child** tag, one per occurrence in the text. `<id>` is unique
  per parent, and the sync flag is part of the name.

Built and parsed by `get_parent_rep_tag`, `get_child_rep_tag`, and `parse_child_rep_tag`. Type detection
(`get_replace_type`, `gen_changing_typebox_get_to_fro`) slices `tag[0:5]` against the 5-char flags. **Toggling
sync renames the tag**: `change_child_tag_sync_flag` deletes the old tag, re-adds a new one over the same range,
and swaps it in the parent's child list. Bindings must then be redone (`setup_rep_bind_tag`).

### State
- `self.replace_tags`: `{parent_or_iso_tag: [option strings]}`, filled by `append_options`.
- `self.rep_replace_tags`: `{parent_tag: [child tag names]}`, filled by `append_child_tags`.
- Both use `utils.append_no_dup`, so re-adding is idempotent.

### Flow
1. Entry points: `add_tag_rep(pattern, opts, sync)` searches the text for every occurrence of `pattern`
   (`utils.return_matches`), and `add_tag_idcs(idx_pairs, opts, name, sync)` takes explicit `"line.col"` start/end
   pairs. If `name` is omitted it uses an auto-counter that starts at 100. Both create child tags and then call
   `setup_rep_bind_tag(parent)`.
2. `setup_rep_bind_tag` computes each child's *target tags*: all synced siblings if the child is synced, otherwise
   only itself. It then calls `setup_rep_bind_tag_attacker`, which binds `<Button-2>`/`<Button-3>` (right click on
   macOS and Linux/Windows respectively) to `gen_options`, Shift+right-click to the sync-preview box, and
   `<Shift-Button-1>` to `change_sync`. It also sets the underline/foreground color by type (`replace_type_dict`,
   `utils.make_darker`).
3. `gen_options` places a `ttk.Frame` of option labels at the click position on `self.master`, so popups are
   siblings of the Text widget, not children. Releasing a click on an option calls `replace_texts` for the target
   tags. Popups are tracked in `self.widget_holder` and destroyed on `<FocusOut>`.
4. `replace_text` → `utils.insert` → `utils.insert_at_end` inserts the new text *inside* the tag's existing range
   before deleting the old text, so the tag survives the replacement. `replace_text` sets the widget to
   `DISABLED` afterward. Callers that insert text must set the state to `NORMAL` first.

### Supporting modules
- `libs/utils.py`: hex color helpers and tk `"line.col"` index arithmetic (`add_to_char_idx` only shifts the
  column, never wraps lines). It also holds the insert/replace helpers above.
- `libs/event_gen.py`: synthetic `event_generate` click helpers used by the GUI tests. The tests use
  `pump_events()` / `update_idletasks()` to flush the Tk event loop instead of calling `mainloop`.
- `libs/BSTTree.py`: a simple synonym BST used only by `demos/BST_GUI.py`. It is not wired into `paraText`.

### Gotchas
- Imports rely on `sys.path.append` of the repo root (`from classes import paraText`, `from libs import utils`).
  There is no package install.
- `utils.short_hex_to_dec` only accepts **uppercase** hex digits. `make_darker` emits non-zero-padded channels
  (e.g. `#123456` → `#91a2b`), and the tests assert this exact output.
- Parsing failures in `parse_child_rep_tag` / `gen_changing_typebox_get_to_fro` call `sys.exit(1)` rather than
  raising.
