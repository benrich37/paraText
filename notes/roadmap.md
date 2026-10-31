# Roadmap and open items

Ordered by priority. Update this file when you finish or discover something. Status as of 2026-10-31.

## Next up (verify what exists)

1. **Live-test each provider route with real accounts.** No live call has been made yet (see `dev_log.md`).
   - `claude-cli`: `["claude", "-p"]` with the prompt on stdin. Believed correct; confirm that it doesn't try to use
     tools, and check its startup latency.
   - `codex-cli`: `["codex", "exec", "-"]`. **Unverified**: confirm that `-` reads stdin in the current Codex CLI.
   - `gemini-cli`: `["gemini"]` with stdin. **Unverified** flags.
   - `gemini` (OpenAI-compatible endpoint `.../v1beta/openai`): confirm the base URL and that `response_format` is
     omitted unless `json_mode`.
   - `anthropic`: confirm that `fallbacks="default"` + `output_config.format` + `effort` are accepted together on
     `claude-opus-5-5`.
   - Then check glossary quality on 2–3 real papers. Are terms copied verbatim, so `find_spans` finds them? What
     share of returned terms fail to match? Log the misses.
2. **Look at the GUI on a real paper** (`paratext read <pdf>`). Check:
   - tooltip placement near the right and bottom screen edges (it currently always opens below-right of the cursor);
   - Retina sharpness: pages render at `zoom` pixels per point, so HiDPI looks soft; multiply by
     `root.winfo_fpixels('1i') / 72`, or use a scale factor;
   - side-panel layout, and Combobox / Entry behaviour.
3. **Reported slow interpreter exit** (once). See `dev_log.md`; recheck in CI timings.

## Improvements

4. Trim the underline to the term's characters. PyMuPDF word boxes include attached punctuation ("(DFT)",
   "potential."); use `get_text("rawdict")` character boxes.
5. Continuous multi-page scrolling, and remembering the last page per document.
6. An "Analyze whole paper" action with progress. Today only the current and next page are requested; mind rate
   limits (2 workers).
7. For Anthropic, consider sending the whole PDF as a `document` block once and asking for a glossary of the whole
   paper. That would handle figures and equations and save repeated context. With per-page calls, use prompt caching
   for the repeated paper context. Read the `claude-api` skill first.
8. A settings dialog in the GUI (provider fields, model, test button) instead of editing TOML. Store API keys in
   `keyring` as an option.
9. Math and symbols: equations extract poorly from PDFs, and symbol terms the model returns may not match any words.
   Consider allowing explanation of the selection only for these.
10. Scanned PDFs have no text layer, so they produce no words. An OCR option via PyMuPDF + Tesseract could fix this.
11. Export an annotated PDF (PyMuPDF annotations) or a glossary appendix.
12. A small eval set for glossary quality (precision of chosen terms, accuracy of explanations, match rate).

## Bigger ideas

13. A web front-end (local server + PDF.js) that reuses `engine.py`. It would give better PDF rendering, text
    selection and hover UX.
14. Bring AI to the original `ParaText` widget: generate audience-specific *replacement* options (rephrasings) for
    spans. This was the 2022 project's vision. `_ISO_` tags are still half-implemented: nothing creates them, and
    shift-click on one would fail in `change_sync`.
