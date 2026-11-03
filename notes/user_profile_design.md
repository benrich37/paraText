# Reader profile: local memory of what the user knows

Written 2026-11-01. Status: v1 implemented (declared profile, prompt integration, editor dialog); the inferred
part (filling the profile from the user's questions) is designed here but not built.

## Goal

Today every explanation is written for a one-line audience ("an undergraduate science student who is not a
specialist…"). The user wants the reader to learn, locally and over time, what *this* reader specialises in,
which concepts they already understand, and which ones need extra hand-holding, and to write explanations
accordingly. Later, highlighting a passage and asking the assistant a question will both answer the question and
feed this profile.

## What the research says

Three bodies of work apply; the full sources are listed at the end.

1. **Learner modelling in tutoring systems.** Classic intelligent tutoring systems keep a *learner model*: an
   overlay of the domain's concepts marked as known / unknown, often with a probability of mastery updated by
   Bayesian Knowledge Tracing from the learner's answers, and a *curriculum graph* with prerequisite links kept
   separately. "Open learner models" (Bull & Kay) make that model visible and editable by the learner, which
   improves trust and accuracy. Recent LLM tutors (DeepTutor 2026, Open TutorAI 2026, LOOM 2025, IntelliCode
   2025) keep the same shape: a persistent per-learner profile of mastery and misconceptions with *provenance*
   (where each belief came from), injected into the prompt of every session; LOOM builds it from everyday
   conversations rather than from declared goals. The recurring caveats: profiles built only from declared goals
   go stale, and inferred mastery needs evidence, not one lucky answer.
2. **Memory layers for LLM assistants.** Mem0, Letta/MemGPT and Zep/Graphiti all follow one loop: after an
   exchange, an LLM pass *extracts* candidate facts about the user, then a *reconciliation* step decides
   ADD / UPDATE / DELETE / NOOP against the existing memory, and retrieval later selects what is relevant. They
   differ in storage (vector store, structured runtime, temporal graph). The two design risks they all name are
   over-extraction (memory bloat, opinions recorded as facts) and stale facts that are never revised. A 2026
   cost analysis finds fact-based memory far cheaper than re-sending long histories.
3. **Vendor memory features** (e.g. Anthropic's `memory` tool) keep memory server-side or model-managed. paraText
   is provider-agnostic and the user wants the memory *local*, so the memory must live in a file the user can
   read and edit, with the model only ever *proposing* changes.

## Design

### The profile is an open learner model stored as TOML

`~/.config/paratext/profile.toml` (or `$PARATEXT_PROFILE`), human-editable, with these sections:

- `background`: one or two sentences in the user's words ("computational chemist, DFT and electrocatalysis;
  weak on electrochemical kinetics").
- `specialties`: areas known deeply. Explanations can use their vocabulary freely.
- `known`: concepts that need no explanation (the glossary skips them; explanations may use them).
- `needs_help`: concepts to explain carefully, prerequisite-first, every time they appear.
- `notes`: free-form observations, each with `source` (`user` or `inferred`), `date`, and for inferred ones the
  `evidence` (the question or paper it came from) and a `confidence`.

v1 implements `background`, `specialties`, `known`, `needs_help` as declared by the user, plus the prompt
integration. `notes` with provenance is reserved for the inferred path.

### How it enters the prompts

`UserProfile.to_prompt()` renders one paragraph that is appended to the system prompt as "About this reader",
and the glossary prompt lists `known` concepts among the terms that need no entry. The audience line stays as
the short framing; the profile adds detail. The profile's fingerprint is part of the engine's cache key, so
editing it regenerates explanations rather than serving stale ones.

### Filling the profile from questions (not built yet)

When the highlight-and-ask feature exists, each answer request also asks the model for a *structured
side-channel*: a small JSON object with `profile_updates` (`add_known`, `add_needs_help`, `note`), each with a
one-line `evidence` and `confidence`. Rules, taken from the memory-layer literature:

1. Extract only from what the user said or asked, never from the paper. A question "what is a Fermi level?"
   is evidence for `needs_help`; "I work with JDFTx daily" is evidence for `specialties`.
2. One question is a hint, not a fact: inferred items start at low confidence and are promoted only when a second
   piece of evidence arrives (a second question on the same concept, or the user confirming).
3. Reconcile, don't append: an update that contradicts an existing item (the user later says they understand
   it) replaces it, with the history kept in `notes`.
4. The user sees and approves: proposed updates appear in the profile dialog as pending suggestions with an
   accept/reject button; nothing inferred changes the prompts until accepted. This is the "open learner model"
   principle and the safeguard against over-extraction.
5. Keep it small: the prompt paragraph is capped (a few hundred words); older low-confidence notes drop out
   first. No vector store is needed at this size; everything is plain text in the prompt.

Concept names should be normalised the same way glossary terms are (`glossary.normalize_term`), so that
"Fermi level" in a question matches the glossary entry and the paper's spans.

### Later possibilities

- Per-paper evidence: which terms the user hovered or clicked repeatedly are weak signals for `needs_help`;
  terms never hovered on pages the user read for a while are weak signals for `known`. Treat these as
  suggestions only.
- A prerequisite graph per paper, built by asking the model which glossary entries depend on which, so an
  explanation of a `needs_help` concept can first explain its unknown prerequisites.

## Sources

- DeepTutor technical report (arXiv 2604.26962): https://arxiv.org/pdf/2604.26962
- LOOM: learner memory graph from daily LLM conversations (arXiv 2511.21037): https://arxiv.org/pdf/2511.21037
- Open TutorAI (arXiv 2602.07176): https://arxiv.org/pdf/2602.07176
- LLM Agents for Education (Findings of EMNLP 2025): https://aclanthology.org/2025.findings-emnlp.743.pdf
- Intelligent tutoring systems playbook (vendor, 2026): https://www.forasoft.com/blog/article/intelligent-tutoring-systems-educators
- Fact-based memory vs long context, cost analysis (arXiv 2603.04814): https://arxiv.org/pdf/2603.04814
- Mem0 overview: https://www.emergentmind.com/topics/mem-0
- Mem0 vs Letta comparison (vendor, 2026): https://vectorize.io/articles/mem0-vs-letta
- Building a custom LLM memory layer: https://towardsdatascience.com/how-to-build-your-own-custom-llm-memory-layer-from-scratch/
