# paraText

paraText expands the context of advanced vocabulary in technical text, so a reader outside the field can follow it
without bouncing between the text and outside references. It started as a CU Boulder *Software Engineering for
Scientists* project (2022; [original project](#the-original-paratext-widget-2022) below) and now also includes a
**PDF reader for scientific papers** that uses an AI model of your choice to explain terms where you read them.

## The paper reader

Open a PDF and paraText underlines the terms on each page that your chosen audience is likely to need explained:

- **Hover** over an underlined term for a short explanation, in the sense the paper uses it.
- **Click** a term to show it in the side panel; **More depth** asks for a fuller explanation.
- **Drag** across any words and press **Explain selection** to have that phrase explained using the surrounding
  passage.
- **Ask about the paper as a whole** in the box under the side panel ("does this paper show that X causes Y?").
  The question goes to the model with the full text of the paper, and the answer says where in the paper the
  support is, or that there is none. Answers are kept per paper, and earlier questions are listed under the latest.
- Change **Explain for:** (e.g. "a high-school student", "a chemist new to electrocatalysis") to retarget everything.

Orange underlines are AI explanations. Blue underlines are acronyms defined in the paper itself ("density functional
theory (DFT)"). These are found without any AI, so the reader is useful even when no provider is set up. Results are
cached per paper, provider, and audience in `~/.cache/paratext/`, so reopening a paper costs nothing.

### Install and run

```sh
pip install -e .                    # add [anthropic] to use Claude through an API key
paratext read paper.pdf             # the GUI (or just: paratext paper.pdf)
paratext install-app                # macOS: add paraText to Finder's "Open With" menu for PDFs
```

On macOS, `paratext install-app` writes `~/Applications/paraText.app`, a thin wrapper around the Python
environment you ran it from. After that, right-click any PDF > Open With > paraText, or use Get Info > "Open with"
> Change All to make it the default PDF viewer. Opening a second PDF replaces the one in the running window. Run
the command again if you move the project or its virtualenv. Output from the app goes to `~/Library/Logs/paraText.log`.

The first time, press **Set up AI…** in the toolbar (or run `paratext setup`). The dialog lists every way to
connect, shows which ones are ready on your machine, lets you paste an API key, pick a model and (where the
provider supports it) a reasoning-effort level, sends a test prompt, and saves the choice to
`~/.config/paratext/config.toml`. Editing that file by hand works too (`paratext config --init` writes a
commented template).

**About you…** opens your reader profile: your background, areas you know deeply, concepts that need no
explanation, and concepts you want explained carefully every time. It is stored locally in
`~/.config/paratext/profile.toml` and added to every prompt, so explanations are pitched at you rather than at a
generic audience. See `notes/user_profile_design.md` for where this is going.

Command-line tools that share the same cache:

```sh
paratext glossary paper.pdf --pages 1-3 [--json]       # build and print a glossary
paratext explain paper.pdf "limiting potential" --page 4 [--detailed]
paratext ask paper.pdf "Does the paper show that the barrier is kinetic?"   # whole-paper question
paratext providers --check                             # list providers and send each a test prompt
```

Every command accepts `--provider NAME` and `--audience "..."`. `--provider none` runs without AI.

### Connecting your AI account

paraText works with any vendor. Consumer chat plans (ChatGPT Plus, Claude Pro/Max, Gemini) don't come with API keys,
so there are three ways to connect:

| Route | Presets | What you need |
|---|---|---|
| **Your chat subscription, via the vendor's own CLI** | `claude-cli`, `codex-cli`, `gemini-cli` | Install [Claude Code](https://claude.com/claude-code), OpenAI's Codex CLI, or Google's Gemini CLI and sign in once. paraText runs it as a subprocess. |
| **A developer API key** (pay per use) | `anthropic`, `openai`, `gemini`, `openrouter` | Set `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GEMINI_API_KEY`, or `OPENROUTER_API_KEY`, and pick a `model` in the config. |
| **A local model** (free, private) | `ollama`, `lmstudio` | Run the local server and set `model`. |

Anything that speaks the OpenAI chat-completions protocol works as a custom server (`kind = "openai"` plus a
`base_url`); any other CLI works as a custom command (`kind = "command"`). API keys entered in the dialog are stored
in the config file, which is made readable only by you; keys in environment variables are used if the field is left
blank. Check that your provider's terms allow this kind of personal scripting.

**Privacy:** the text of each page you open (and of the first page, as context) is sent to the provider you select.
Use a local model for papers you can't share.

## The original paraText widget (2022)

The objective of this project is to write an application that expands contextual information of advanced vocabulary
found in technical texts. The user right clicks on an underlined word for replacement options. The user would then
shift and click to toggle sync options for the highlighted word. When the text is red, this indicates that all
instances of that word has been replaced with the same options. If the text is in yellow, this indicates that the
change for the text is unique and will not trigger changes in other instances of the word.

The motivation of this project is based on the need to make technical writing more accessible to a general audience.
Communication of an educated audience requires specific vernacular native to that field. This is different for an
uneducated audience where communication requires additional context. Our goal for this project is to create an
expandable text interpretation tool for increasing accessibility to scientific texts. We have designed a Python GUI as
the prototype for future HCI projects that aim to create interactive texts that provide contextual meaning for any
targeted audience.

As science continues to grow rapidly with new fields and knowledge, so does the complexity of the vocabulary. For the
uneducated audience, too much time is spent on re-reading text and using outside resources to patch together a
contextualized understanding. The result is that the learning experience is fragmented and often co-dependent on
several resources. paraText attempts to eliminate this through the use of an interactive text that gives replacement
options for confusing phrases and words outside of everyday vernacular.

<p align="center">
   <img src="https://user-images.githubusercontent.com/91628000/206314640-c4285ff6-91e2-4e8c-b529-abb598c202ca.png" width=75% height=75%>
</p>

This screen recording shows how it works. The words highlighted in red are synced, meaning that if one of them is
changed, all instances of that word will be changed. If it's yellow, only one instance of the word will be changed.

https://user-images.githubusercontent.com/91628000/206312726-d8b5bc65-f743-4a87-8cc3-4c8e8ae6e28d.mov

Run the demos after `pip install -e .`:

```sh
python demos/demo_a.py          # every occurrence of a pattern (add_tag_rep)
python demos/demo_b.py          # explicit index ranges (add_tag_idcs)
python demos/synonym_lookup.py  # BST-backed synonym lookup
```

The widget is `paratext.widget.ParaText`, a `tkinter.Text` subclass.

## Development

```sh
pip install -e ".[dev]"
python -m pytest                 # reader tests run headless (Qt offscreen); legacy Tk tests skip without a display
pre-commit run --all-files       # yaml / end-of-file / whitespace / ruff
```

The reader is built with Qt ([PySide6](https://doc.qt.io/qtforpython-6/), LGPL) and renders pages with
[PyMuPDF](https://pymupdf.readthedocs.io), which is licensed under the AGPL (commercial licenses are available from
Artifex). Keep this in mind before distributing paraText.
