# Roadmap and open items

Ordered by priority. Update this file when you finish or discover something. Status as of 2026-11-04. Also check `ReportedIssues.md` for issues logged from the reader.

## Next up (verify what exists)

0. **Look at the Qt reader and the setup dialog on screen** (`paratext read <pdf>`, `paratext setup`). Nothing
   has been seen with human eyes yet; everything was verified offscreen. Check: toolbar layout on macOS, dark
   mode, tooltip contrast, dialog field widths, that the "Fit width" zoom on open looks right on a Retina display.

1. **Live-test each provider route with real accounts.** No live call has been made yet (see `dev_log.md`).
   - `claude-cli`: `["claude", "-p"]` with the prompt on stdin, model via `--model X`, effort via `--effort Y`.
     Verified 2026-11-04 (Claude Code 2.1.318, about 1.6 s for a one-word reply). Still to check: that it does
     not try to use tools on a long prompt.
   - `codex-cli`: `["codex", "exec", "-"]`, model via `-m X`. **Unverified**: confirm that `-` reads stdin in the
     current Codex CLI.
   - `gemini-cli`: `["gemini"]` with stdin, model via `-m X`. **Unverified** flags.
   - `openai` effort: `reasoning_effort` values (`low`/`medium`/`high`) and which models accept it.
   - `gemini` (OpenAI-compatible endpoint `.../v1beta/openai`): confirm the base URL and that `response_format` is
     omitted unless `json_mode`.
   - `anthropic`: confirm that `fallbacks="default"` + `output_config.format` + `effort` are accepted together on
     `claude-opus-5-5`.
   - Then check glossary quality on 2–3 real papers. Are terms copied verbatim, so `find_spans` finds them? What
     share of returned terms fail to match? Log the misses.
2. **Scroll performance on a long paper**: pages render on one background thread at the effective scale
   (capped at 4×); check that fast scrolling and zooming feel fine on the 65-page Bazant paper, and tune
   `PixmapCache.limit` / `MAX_RENDER_SCALE` if memory grows.
3. **Reported slow interpreter exit** (once, tkinter era). See `dev_log.md`; recheck in CI timings.
3b. **macOS app bundle** (`paratext install-app`, done 2026-11-03): check on screen that the Dock and menu bar say
   "paraText" (not "python3"), that dropping a PDF on the Dock icon works, and that `claude -p` is found when the
   app is started from Finder. Possible follow-ups: open each PDF in its own window instead of replacing; a
   proper Launch-Services-friendly binary (py2app) if the `shell-script`/`launch-disabled` flags ever bite.

## Improvements

4. Trim the underline to the term's characters. PyMuPDF word boxes include attached punctuation ("(DFT)",
   "potential."); use `get_text("rawdict")` character boxes.
5. Remember the last page per document (continuous scrolling is done).
6. Progress display for "Explain whole paper" (today: a status-bar count); mind rate limits (2 workers).
7. For Anthropic, consider sending the whole PDF as a `document` block once and asking for a glossary of the whole
   paper. That would handle figures and equations and save repeated context. With per-page calls, use prompt caching
   for the repeated paper context. Read the `claude-api` skill first.
8. Store API keys in the system keychain (`keyring`) as an option; today the setup dialog writes them to the
   0600 config file. Also: a "sign in" button that runs the vendor CLI's login for the subscription options.
9. Math and symbols: equations extract poorly from PDFs, and symbol terms the model returns may not match any words.
   Consider allowing explanation of the selection only for these.
10. Scanned PDFs have no text layer, so they produce no words. An OCR option via PyMuPDF + Tesseract could fix this.
11. Export an annotated PDF (PyMuPDF annotations) or a glossary appendix.
12. A small eval set for glossary quality (precision of chosen terms, accuracy of explanations, match rate).

## Reader profile (see `notes/user_profile_design.md`)

15. **Highlight and ask.** A question box for the current selection (or a term) that answers in context and
    keeps a per-paper Q&A history in the side panel. This is the feature that will feed the profile.
    *Partly done 2026-11-03:* the "Ask about the paper as a whole" box (`ContextEngine.ask`, `paratext ask`)
    answers from the full text and stores the history in the cache file; the panel lists earlier questions under
    the latest answer. Still to do: tie a question to the current selection/term, follow-up questions that see the
    previous answer, and a nicer history view than plain text. For Anthropic, prompt caching of the paper block
    would make repeated questions much cheaper (see item 7).
16. **Inferred profile updates.** With each answer, request a structured side-channel of proposed profile
    updates with evidence and confidence; show them as pending suggestions in the profile dialog; promote only
    on a second piece of evidence or user acceptance. Store accepted and rejected ones in `notes` with
    provenance.
17. Weak signals from reading behaviour (repeated hovers → `needs_help`), as suggestions only.
18. Per-paper prerequisite graph between glossary entries, so a `needs_help` concept is explained after its
    unknown prerequisites.

## Linked files (done 2026-11-04: `links.py`, side-panel list, `paratext links`)

19. Use linked SI PDFs in "Ask about the paper" (append their `full_text` under a budget) and offer their terms
    in the glossary; show a linked PDF's page count and title in the list; drag-and-drop onto the list.

## Bigger ideas

13. A web front-end (local server + PDF.js) that reuses `engine.py`, if a browser-based or remote UI is ever
    wanted. Not needed for desktop use now that the reader is on Qt.
14. Bring AI to the original `ParaText` widget: generate audience-specific *replacement* options (rephrasings) for
    spans. This was the 2022 project's vision. `_ISO_` tags are still half-implemented: nothing creates them, and
    shift-click on one would fail in `change_sync`.
