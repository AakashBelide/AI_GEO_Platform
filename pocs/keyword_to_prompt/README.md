# POC: `keyword_to_prompt` — keyword → prompt bootstrapping (Task R3)

The cheap seeding trick (Otterly/Semrush): turn an existing SEO **keyword list** into
natural-language **prompts** and merge them into the R1 set — deterministic, offline, no keys.

## What it does
- **Infers intent from modifiers**, not from an LLM: commercial modifiers (`best`, `pricing`,
  `vs`, `review`, `buy`, …) → *commercial*; a brand name in the keyword → *navigational*
  (or *commercial* for "{brand} vs / pricing"); otherwise → *informational*. This keeps the R1
  intent labels and skew guard (R1.3/R1.4) meaningful for keyword-sourced prompts too.
- **Wraps each keyword** in a question frame per intent (`max_variants` picks how many frames).
- **Merges + de-duplicates** into an existing R1 prompt set on a normalized key (casefold,
  collapsed whitespace, trailing punctuation stripped), so `crm` and `What is CRM?` don't
  double-count. Order is preserved: existing set first, then new keywords in input order.

## Honesty note
Modifier matching is **whole-token** (`buyer` does not trigger `buy`). The output is an
intent-labeled *draft* for human curation — it is not claimed to reproduce real search intent.

## Run
```bash
uv run pytest pocs/keyword_to_prompt/ -q     # 14 tests, offline
```

## Integrates with
Reuses `pocs/onboarding` (`Prompt`, `BrandProfile`); output feeds the same downstream path as
R1 — `pocs/connectors` (one `runs` row per engine call) → `pocs/metrics` (rates with CIs).
