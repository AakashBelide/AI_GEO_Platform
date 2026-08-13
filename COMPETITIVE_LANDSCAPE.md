# GEO Competitive Landscape: How the Industry Actually Builds These Products

*Companion to RESEARCH.md. Prepared for the same graduate course ("Computational Skepticism for AI"). Based on deep research across ~28 commercial GEO/AI-visibility tools, current as of August 2026. As in RESEARCH.md, claims are flagged **[VERIFIED]** (vendor's own product/pricing/docs pages), **[VENDOR]** (marketing claim, not independently verifiable), or **[3P]** (third-party review/estimate, directionally reliable but not authoritative).*

---

## TL;DR

- **The dominant product is NOT a "paste a URL and scan the whole site" tool.** That's the SEO-auditor mental model, and it's a minority pattern here. The category center of gravity is **brand-first, prompt-based answer monitoring**: enter a brand + domain + a few competitors → the tool auto-generates a set of AI-search prompts → it runs those prompts against multiple engines on a schedule → it reports mention rate, citation rate, and share-of-voice.
- **Keyword tracking, as a standalone GEO product, barely exists.** Keywords survive only as raw material that gets *converted into* prompts (Otterly, Semrush "Prompt Research"). The SEO-incumbent tools (SE Ranking, Nightwatch) that still require manually-typed keywords are viewed by reviewers as the least GEO-native of the field.
- **The action layer — actually writing/publishing fixes, not just diagnosing them — is the biggest split in the market**, and it roughly doubles-to-10x's the price. Roughly half of ~28 tools profiled are monitor-only.
- **Not one of the ~28 tools reports statistical confidence** (confidence intervals, sample sizes, run-to-run variance) despite documented 40–60% monthly citation drift. This is the single clearest, most defensible gap for an independent builder, and it is independently corroborated by a 2026 Digiday piece on marketer skepticism and by academic work reporting 5–7 percentage-point CIs on citation share that no vendor discloses.
- **For a solo/small builder, the realistic, buildable wedge is not "build a better Profound."** It's a narrow, technically honest tool that does one of the underserved things well: rigorous variance reporting, causal-attribution testing, or cross-engine reconciliation — the three gaps every large vendor has left untouched.

---

## 1. THE FIVE PRODUCT ARCHETYPES

Every tool profiled falls into one of five archetypes, distinguished chiefly by **what you type in first** (the onboarding input) and **what the product's core artifact is**.

### Archetype 1 — Answer-side brand/prompt visibility trackers (the market center of gravity)
**Onboarding flow:** domain or brand name → tool auto-drafts a brand profile → auto-suggests ~5–10 competitors → auto-drafts a prompt set → user curates → tool runs those prompts across engines on a schedule → reports mentions, position, share-of-voice, sentiment, cited sources.

**Members:** Profound, Peec AI, AthenaHQ, Otterly.ai, LLMrefs, Rankscale, Brandlight, Waikay, Knowatoa.

This is the largest archetype by tool count and the one nearly every "best GEO tools" listicle treats as the default shape of the category. It is fundamentally a **monitoring instrument**, not a scanner or a publisher — most members explicitly do not crawl the client's site and do not auto-execute content changes.

### Archetype 2 — Statistical brand-index / "AI market research"
**Onboarding flow:** demo-led → brand + product category → tool runs **thousands of prompt simulations across ~10–11 models** → returns an aggregated benchmark score rather than tracking individual live queries day-to-day.

**Members:** Evertune (the defining example), Ahrefs Brand Radar (leans this way given its 260M+-prompt database).

This is the archetype closest in spirit to your RESEARCH.md's rigor thesis. **Evertune** positions itself as "Nielsen for AI answers" — proprietary sampling across ~11 systems, thousands of runs per report, a consumer panel of ~150M prompts. It is the only vendor found that treats *sample size and repeated sampling* as a first-class design choice rather than an afterthought. It still does **not publish confidence intervals or explicit uncertainty bounds** to the customer — the sampling is used to produce a more stable point estimate, not a reported range. That gap is the opening.

### Archetype 3 — Site-side / "agent-experience" optimization + action layer
**Onboarding flow:** connect a site/domain → tool crawls it as an AI bot would → diagnoses crawlability blockers (robots.txt, JS-rendering, GPTBot/ClaudeBot/PerplexityBot access) → in the strongest case, actively serves an optimized version of the content to bots.

**Members:** Scrunch AI (strongest — genuinely executes via its CDN-layer AXP), Goodie AI (audit + content generation), Lumar (enterprise crawler + GEO diagnostics), Rankscale, Knowatoa, Trakkr, Conductor.

This is the archetype closest to the "paste a URL, scan the whole site" mental model you started with — but it is a **minority pattern**: only about 6 of the ~28 tools profiled do real AI-bot crawlability auditing at all. Scrunch is the standout because its AXP module doesn't just *report* a crawlability problem — it serves AI bots a separate, machine-readable version of the page at the CDN level (the vendor disputes this constitutes cloaking).

### Archetype 4 — Incumbent SEO suites bolting on AI visibility
**Onboarding flow:** user is already inside an existing SEO suite; keywords/prompts are layered onto the suite's pre-existing site-audit + rank-tracking crawler.

**Members:** Semrush AI Toolkit, Ahrefs Brand Radar, SE Ranking, Nightwatch, BrightEdge, Conductor.

These are legacy SEO platforms (large existing user bases, deep data assets) retrofitting GEO as an add-on module (Semrush: +$99/mo; Ahrefs: $199–699/mo per platform). They most literally combine "(a) crawl the whole site" and "(d) keyword tracking" because that's their inherited DNA — AI-answer monitoring is bolted on top, not native. Reviewers consistently rate these as the shallowest on AI-specific depth despite the largest data assets.

### Archetype 5 — SMB/self-serve lightweight monitors & execution/agency hybrids
Low-cost, brand-name-in, monitor-only tools (Otterly $29, Waikay $19.95, LLMrefs free tier, Rankscale $20) — functionally a cheaper slice of Archetype 1. A separate sub-group blurs into **content production/agency services** rather than software (Phantom's third-party blog network, SEO Stuff's done-for-you packages, Gauge's publish-and-measure loop) — these sell execution, not just measurement.

---

## 2. HOW BRAND-NAME INPUT BECOMES A PROMPT SET

Three distinct techniques recur across vendors:

1. **Domain/topic crawl → derived prompts.** The tool crawls the domain, extracts entities/topics, and drafts prompts from them (AthenaHQ, Peec, Writesonic, Conductor's persona-based synthetic prompts).
2. **Mapped against a real-user-prompt database or panel.** Vendors with large proprietary datasets match your brand/category against prompts real users actually typed to AI systems (Ahrefs' 260M+-prompt database, Semrush's 289M captured prompts, Profound's 100M-prompt panel, Evertune's ~150M-prompt consumer panel, LLMrefs' "fan-out from real conversations"). This is generally viewed as higher-fidelity than a purely generative approach.
3. **Keyword-to-prompt conversion.** Existing SEO keyword data is transformed into natural-language prompts (Otterly, Semrush "Prompt Research").

**A near-universal criticism across independent reviews:** auto-generated prompt sets skew toward *branded* queries (i.e., prompts that already contain your brand name) rather than the *unbranded, category-level* questions where visibility actually matters competitively. Multiple third-party reviewers flag this for Scrunch, Otterly, and others — manual curation is treated as mandatory, not optional, everywhere.

Almost every vendor that generates prompts then computes **share-of-voice vs. a confirmed competitor set** — this is the category's universal headline metric. Notably, Brandlight's own documentation concedes that its share-of-voice metric is "a proxy, not attribution" — a rare vendor admission that mention frequency is not the same as causal marketing impact.

---

## 3. SITE-SIDE AUDITING vs. ANSWER-SIDE-ONLY

This is the cleanest fault line in the market for anyone thinking about "does it scan the whole site."

**Do real AI-bot crawlability auditing** (robots.txt, GPTBot/ClaudeBot/PerplexityBot access, JS-rendering issues, sometimes llms.txt):
Scrunch (executes, not just audits), Goodie AI (llms.txt + crawler audit), Lumar (enterprise-grade, tied to a deep crawler), Rankscale (200+ factors), Knowatoa (AI Search Console tests 15+ bot types), Trakkr (explicit "fix robots.txt for GPTBot" actions + llms.txt generator), Conductor ("AI Bot Crawling Reports"), Semrush (AI Search Site Audit).

**Answer-side monitoring only — no site crawl at all:**
Profound (has server-log bot *analytics*, but that's observability, not an audit of your allow/disallow configuration), Peec AI (explicitly confirmed by three independent reviews to do no crawl/robots.txt analysis), Otterly (crawler simulation exists but explicitly does not check robots.txt per its own docs), LLMrefs (only a bolt-on standalone checker), Ahrefs Brand Radar, SE Ranking, Nightwatch, AthenaHQ (claims crawlability auditing in marketing, but reviewers could not reproduce it), Bluefish, Daydream, AirOps.

**The practical implication:** if your instinct was "GEO tool = crawl the site, find problems, fix them," you were describing the *minority* archetype (3), not the market's dominant shape. Most of the money in this space is being paid for **answer monitoring**, not site auditing.

---

## 4. THE ACTION LAYER: WHO CLOSES THE LOOP

This is where the market genuinely splits, and where price scales hardest.

- **Monitor-only** (report mentions/citations/SoV, give at most a to-do list): Peec, Otterly, LLMrefs, Rankscale, Ahrefs Brand Radar, Bluefish (disputed — vendor claims optimization, one review calls it monitor-only in practice), Nightwatch, SE Ranking (light tips only).
- **Monitor + recommend** (prioritized fixes, but the human executes): Profound (core), Semrush, Knowatoa, Rankscale, BrightEdge, Lumar (turns issues into dev tickets).
- **Monitor + generate/execute content**: Gauge (generates content, publishes to CMS, re-measures), Writesonic (article generation + agentic workflows on Enterprise), AirOps (strongest content-workflow execution via its Quill agent), Profound Agents (separate module — publishes targeting specific losing prompts), Conductor Creator, Goodie (content studio, but founder concedes "someone still has to act on them").
- **Executes at the infrastructure/serving layer, not the content layer**: Scrunch's AXP (serves bots a different version of the page without touching the human-facing content) — arguably the only tool that "executes" in a fully automated, no-human-in-the-loop sense.
- **Execution via human agency, not software**: Phantom (autonomous blog network, but still a managed content pipeline), SEO Stuff (done-for-you guest posts/articles).

**The universal, load-bearing finding:** across every vendor examined, **no tool convincingly closes the loop from "we changed the content" to "we proved that change caused the visibility increase."** Every action-layer tool shows before/after dashboards; none run a controlled experiment (holdout prompts, A/B content variants, matched time windows) to separate the effect of the edit from ordinary volatility. This is precisely the causal-attribution gap RESEARCH.md §1.3 identifies, and it is confirmed, not merely inherited, by this deeper competitive pass.

---

## 5. ENGINE COVERAGE PATTERNS

The near-universal baseline across nearly all 28 tools is **ChatGPT + Perplexity + Google AI Overviews**. Differentiation happens in the long tail:

- **Broadest coverage:** Goodie AI (up to 11: adds Claude, Gemini, AI Mode, Copilot, Grok, Meta AI, Amazon Rufus, DeepSeek), Rankscale (17+, inflated by counting API model variants separately), Evertune (~10–11), Profound/Scrunch/AthenaHQ (7–9).
- **Notable gaps at entry tiers:** Otterly's cheapest tier omits Gemini/Copilot/Claude; Semrush covers only 4–5 engines even on its paid toolkit; Ahrefs covers 5–6; Writesonic covers only 3 engines below Enterprise (a frequently-cited "gotcha" in reviews).
- **Claude coverage is the most commonly paywalled/gated engine** — Semrush, Peec, Otterly, and Scrunch all reserve it for higher/enterprise tiers; Nightwatch and Trakkr are unusual in including it on every tier.
- **Engine count is explicitly used as an upsell lever** almost everywhere: base tiers get 3–5 engines, "Enterprise" unlocks the rest.
- **Google AI Overviews has no official consumer API for any vendor.** Every tool either scrapes it (ToS risk) or uses Gemini's Search-grounding API as a documented proxy — this constraint applies to the entire industry, not just a solo builder (see RESEARCH.md §3.3).

---

## 6. PRICING BANDS (CONSISTENT ACROSS ~28 TOOLS)

| Band | Range | Examples |
|---|---|---|
| **Free / one-off audits** | $0 | HubSpot AEO Grader, Trakkr free tier, Knowatoa free tier, CapstonAI free scan |
| **SMB / self-serve entry** | ~$20–$99/mo | Rankscale $20, Otterly $29, Waikay $19.95, LLM Scout $39.99, Peec $80–89, Profound $82–99, Semrush add-on $99, Nightwatch €79 |
| **Mid-market** | ~$100–$800/mo | Peec $199–499, Knowatoa $199, Scrunch $250–500, AthenaHQ $295, Ahrefs bundle $699, Goodie $399, Evertune $800, Gauge $599 |
| **Enterprise** | Custom, typically $2,000–$25,000+/mo | Profound, AthenaHQ, Lumar (~$2.6k+), Evertune (~$3k floor per 3P), Brandlight ($4k–$25k per 3P), BrightEdge ($25k–$150k/yr per 3P) |

Only a minority of vendors (Peec, Profound, Semrush, Rankscale, Knowatoa, Goodie, Evertune, Otterly, LLMrefs, Trakkr, Writesonic) publish real self-serve prices; most enterprise-oriented tools (Conductor, BrightEdge, Bluefish, Daydream, Brandlight) are quote-only, and every "enterprise" figure above ~$2,000/mo in this document is a third-party estimate, not a vendor-published number.

---

## 7. WHAT AN INDEPENDENT BUILDER CAN ACTUALLY USE

This section translates the landscape into concrete, buildable decisions for a solo or small-team project, consistent with RESEARCH.md §5.

### 7.1 What's genuinely reusable / learnable from the industry

- **The onboarding pattern is validated and worth copying:** brand/domain → auto-suggest competitors → auto-draft prompts → user curates. This is table stakes UX; building it isn't a differentiator, but skipping it (e.g., forcing users to hand-type 50 prompts with no assistance) would feel primitive next to every competitor.
- **The core metric set is validated and standard:** mention rate, citation rate, share-of-voice, position, sentiment. Reuse these definitions rather than inventing new ones — they're what any potential user or evaluator will already expect, and RESEARCH.md §4.1 already defines them compatibly (adding Position-Adjusted Word Count and Subjective Impression from the Princeton paper as a research-grade upgrade).
- **The keyword-to-prompt conversion technique** (Otterly, Semrush) is a cheap, useful bootstrapping trick if a user already has SEO keyword data and no prompt list.
- **Server-log-based AI-bot analytics** (Profound's Agent Analytics, Scrunch's Agent Analytics) is a good pattern to know about but is out of scope for a solo prototype — it requires the user's own CDN/server log access, which a course project won't have for arbitrary domains.

### 7.2 The three genuinely open lanes (where nobody in ~28 tools competes well)

These map directly onto RESEARCH.md's own gap analysis (§1.3) and are now independently confirmed at much greater competitive depth:

1. **Statistical rigor / uncertainty reporting.** Zero of ~28 tools show confidence intervals, sample sizes, or explicitly flag "these two brands are not statistically distinguishable." Evertune is the closest (thousands of sampling runs) but still reports only a point-estimate index, not a range. **This is the single most defensible, literally-uncontested differentiator available**, and it is also the cheapest to build — it requires no new data source, only honest treatment of data every competitor already collects. A 2026 Digiday piece documents marketers' own skepticism of these tools' inconsistent results, and academic work reports 5–7 percentage-point CIs on citation share that no vendor discloses — both independently corroborate that this gap is real and felt by the market, not merely theoretical.
2. **Causal attribution.** No tool proves a content edit *caused* a citation increase rather than merely preceding one during normal volatility. Building even a small controlled before/after test (the Princeton paper's method, scaled down) would be a genuine research contribution nothing in the commercial market offers.
3. **Cross-engine reconciliation with transparent methodology.** Every vendor's "share of voice" is computed slightly differently (API vs. scraped UI vs. panel data), and none of them publish their sampling methodology in a way a skeptical buyer could audit. A tool that is explicit and reproducible about its method — even at smaller scale — would stand out in a market several reviewers describe as opaque and difficult to trust.

### 7.3 What is NOT buildable solo, and why

- **Whole-site crawling + rendering + technical audit at Lumar/Scrunch depth.** These require enterprise-scale crawler infrastructure, JS-rendering pipelines, and CDN-level integrations (Scrunch's AXP). Out of scope for 15–20 days.
- **A real-user-prompt database** (Ahrefs' 260M+, Semrush's 289M, Profound's 100M, Evertune's 150M panel). These are the vendors' core moats, built over years from proprietary traffic/partnership data. A solo project cannot replicate this and should not try — use a hand-curated 30–50 prompt set instead (RESEARCH.md §5.2), which is methodologically fine for a course project since the goal is measurement rigor, not corpus scale.
- **Server-log-based AI-bot analytics** (Profound/Scrunch Agent Analytics) — requires access to a real production site's CDN/server logs, which a course project targeting arbitrary example brands won't have.
- **An automated "detect → rewrite → publish → verify uplift" loop.** Confirmed above: *no vendor in the entire market* has convincingly built this, at any budget. Attempting a simplified, honestly-scoped version of just the "verify uplift" piece (via a controlled before/after test) is far more tractable and valuable than trying to build the full loop.
- **Consumer-panel-style demographic weighting** (Evertune's approach) — requires a panel product/partnership; not accessible to a solo builder.

### 7.4 Constraints that apply industry-wide (not just to a solo project)

- **Google AI Overviews has no sanctioned API for any vendor.** Every competitor either scrapes it (ToS risk, brittleness) or proxies it via Gemini's Search-grounding API and documents the discrepancy. A solo builder should do exactly what the RESEARCH.md recommends: use the Gemini proxy, document it, and never scrape Google.
- **LLM outputs are non-deterministic even at temperature 0** (floating-point non-associativity + batching), so no vendor — regardless of budget — can claim a perfectly reproducible single-run score. This is a structural property of the underlying models, not an engineering gap any competitor has actually solved; it only means the *reporting* of that uncertainty is optional and everyone has chosen to skip it.
- **Sourcing can shift discontinuously from legal/business events**, independent of any tool's engineering (e.g., Reddit's citation share on Perplexity dropping 86% after the Reddit v. Perplexity lawsuit). Any GEO tool's historical trend data can be invalidated by an external event outside its control — a caveat worth stating explicitly in a course project rather than assuming stable baselines.
- **Prompt-based pricing scales expensive fast** — a recurring complaint across nearly every reviewed tool (Peec, Otterly, Semrush) is that meaningful prompt volume (100s of prompts across several engines with repeats for variance) gets costly quickly. This validates RESEARCH.md §4.4's design implication: prioritize paraphrase/model/engine *breadth* over repeated-prompt volume, both for cost and for statistical efficiency.

---

## 8. BOTTOM LINE

The GEO tooling market has converged hard on one product shape — **brand-in, auto-generated prompts, cross-engine mention/share-of-voice tracking** — delivered at price points from $20/mo self-serve to $25k+/mo enterprise, built by companies with proprietary prompt databases and crawler infrastructure a solo builder cannot replicate. But the market is uniformly weak exactly where RESEARCH.md's thesis says it should be: **no vendor, at any price tier, reports statistical confidence, proves causation, or transparently reconciles cross-engine methodology.** That triangle — cheap to build, structurally absent from ~28 competitors, and independently corroborated by both journalism (Digiday) and academic work — is where a 15–20 day solo project should sit. The right scope is not "build a cheaper Profound"; it's "build the one honest measurement the entire industry has chosen to skip."
