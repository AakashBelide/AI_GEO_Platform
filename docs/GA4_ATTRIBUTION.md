# AI-referral attribution in GA4 (Task A3 — documentation only)

**Status: documentation, not implemented.** This project is local-only and has no live GA4
property, so this is the *method* for detecting AI-answer-engine referral traffic in Google
Analytics 4 — the demand-side complement to the platform's supply-side citation measurement.
It is written to be honest about what this can and cannot tell you (see §4).

## 1. Why this is separate from the rest of the platform
The `geo run` pipeline measures **whether AI engines cite you** (supply side: did ChatGPT /
Perplexity / Gemini mention or link your domain). GA4 attribution measures **whether people then
click through to your site from those engines** (demand side). They answer different questions and
neither substitutes for the other — a brand can be cited heavily yet get almost no referral clicks
(and vice-versa). This doc covers only the demand side.

## 2. The detection method — a regex custom channel group
GA4 does not, by default, break out "AI assistants" as a channel; those sessions mostly land in
**Referral** or **Direct**. Create a **custom channel group** (Admin → Data display → Channel
groups) with a channel defined by the **`Session source`** matching a regex, ordered *above*
Referral so it captures first:

```
# Channel: "AI Assistants"  — Session source matches regex (case-insensitive):
chatgpt\.com|chat\.openai\.com|openai\.com|perplexity\.ai|gemini\.google\.com|
bard\.google\.com|copilot\.microsoft\.com|bing\.com/chat|claude\.ai|
poe\.com|you\.com|phind\.com|arc\.net
```

Notes:
- Match **source**, not medium (these arrive as `referral` medium, sometimes `(none)`).
- Keep the list versioned — new assistants and hostname changes appear often (e.g. the
  `chat.openai.com` → `chatgpt.com` migration).
- In **Explore**, this custom channel group then works as a dimension for a free-form report:
  sessions, engaged sessions, conversions, by AI-assistant source.

### Explore / report recipe
1. Explore → Free-form. Dimension: your custom channel group (or `Session source` filtered by the
   regex above). Metrics: Sessions, Engaged sessions, Key events/Conversions.
2. Secondary dimension `Landing page + query string` to see **which pages** AI referrals hit —
   cross-reference with the pages the citation pipeline shows engines *citing*.
3. Trend it over time to watch AI-referral share grow relative to Organic Search.

## 3. Cross-referencing with this platform (the useful bit)
The honest, combined view — which neither side gives alone:

| Supply (this platform) | Demand (GA4) | Reading |
|---|---|---|
| High citation rate | High AI-referral sessions | Working end-to-end. |
| High citation rate | ~0 AI-referral sessions | You're cited but not clicked — the answer satisfies the user in-engine (or links elsewhere). |
| Low/0 citation rate | Some AI-referral sessions | Referrals from engines/pages you're not measuring; widen the prompt set. |

The live Asana finding (`docs/OBSERVATIONS_AND_ANALYSIS.md`, O-8) is exactly why this matters:
OpenAI/Anthropic mention the brand but cite `asana.com` 0% — a supply-side gap that would show up
on the demand side as *mentions you can't attribute a click to*.

## 4. Honest limitations (read before trusting any number)
- **Dark traffic.** Many AI referrals arrive with no referrer and land in **Direct**, so GA4
  *undercounts* AI-driven visits. The regex channel captures only sessions that carry an
  identifiable AI source. Treat the number as a **lower bound**, never a total.
- **Source spoofing / privacy.** Referrer stripping, in-app browsers, and consent-mode denials all
  hide or drop the source. Numbers are directional.
- **Correlation, not causation.** A rise in AI-referral sessions after a content edit is *not*
  proof the edit caused it — background trends move too. Pair it with the controlled before/after
  test (`pocs/causal`, Task O2) before claiming impact.
- **No PII.** This is a method note; no analytics data, property IDs, or user data are stored in
  this repo.

## 5. Reference
Method summarized from `RESEARCH.md` §4.3. This file is the A3 deliverable (documentation-only);
there is no code to run.
