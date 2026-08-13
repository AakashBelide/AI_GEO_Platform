# Building a Generative Engine Optimization (GEO) Platform: Research Report & Platform Design

*Prepared for a graduate course, "Computational Skepticism for AI." Throughout, claims are tagged as **PROVEN** (controlled experiment), **CORRELATIONAL** (large-scale observational), or **SPECULATED/FORECAST** (prediction or single-vendor anecdote). Current as of July 2026.*

## TL;DR
- **GEO is a real, fast-growing product category, but its evidence base is thin.** The AI-visibility tooling market raised $300M+ between mid-2025 and spring 2026, led by Profound (which raised a $96M Series C led by Lightspeed Venture Partners at a $1B valuation, announced Feb 24, 2026, bringing total funding past $155M). The one *proven* fact underpinning the whole category — that content can be deliberately optimized to be cited more by AI engines — comes from a single rigorous academic study (Princeton/KDD 2024). Almost everything else in vendor marketing is correlational or anecdotal.
- **For a solo 15–20 day project, build ONE thing: a cross-engine citation-tracking harness.** Run a fixed prompt set through the OpenAI Responses API (`web_search` tool), Perplexity Sonar API, and Gemini API (Google Search grounding), parse each engine's structured citation annotations, and log which domains/brands get cited — with repeated runs to quantify non-determinism. This is the highest-value, lowest-effort, Terms-of-Service-clean component and it directly demonstrates the "computational skepticism" theme.
- **The single most important epistemic caveat:** AI answers are non-deterministic and volatile — Profound reports "roughly 40–60% of the domains cited in AI responses will be completely different just one month later, even for identical questions." Any GEO metric is therefore a noisy estimate, not a measurement. A credible platform must report confidence intervals and sample sizes, not single-run "scores." Most commercial tools do not.

---

## 1. LANDSCAPE & DEFINITION

### 1.1 What GEO is and how it differs from SEO
Generative Engine Optimization (GEO) is the practice of optimizing content so it is retrieved, synthesized, and **cited** by AI answer engines (ChatGPT, Perplexity, Google AI Overviews/AI Mode, Gemini, Claude, Microsoft Copilot) rather than merely ranked in a list of blue links. The term was coined in the Princeton paper "GEO: Generative Engine Optimization" (Aggarwal, Murahari, Rajpurohit, Kalyan, Narasimhan & Deshpande, KDD 2024, arXiv:2311.09735), which formalized the "generative engine" as a system that "satisfies queries by synthesizing information from multiple sources and summarizing them using LLMs."

Practical differences from SEO:

| Dimension | Traditional SEO | GEO |
|---|---|---|
| Goal | Rank in a list of links | Be cited/mentioned inside a synthesized answer |
| Unit of success | Position (rank 1–10) + click | Share of answer / citation frequency / mention |
| Output | Deterministic SERP (largely stable) | Non-deterministic generated text (varies run-to-run) |
| Signal focus | Backlinks, keywords, technical SEO | Brand mentions, quotability, statistics, structure, third-party presence |
| Measurability | Mature (rank trackers, GSC) | Immature, probabilistic, no ground-truth index |

The field also uses "AEO" (Answer Engine Optimization) and "LLM SEO" roughly interchangeably; GEO is the term with academic provenance.

### 1.2 Why it matters now
The shift is documented and material, though magnitudes are contested:

- **Adoption.** Per Search Engine Land (Feb 27, 2026), "ChatGPT now has more than 900 million weekly active users, OpenAI announced" — disclosed alongside a $110B funding round, up from 400M in February 2025; the app crossed 1 billion monthly active users in June 2026 (Sensor Tower data via Reuters). Google's Gemini app passed 900M monthly active users at I/O 2026, and Google's AI Overviews reach roughly 2.5 billion people monthly. These are mainstream discovery surfaces, not niche tools.
- **Zero-click behavior (CORRELATIONAL/experimental).** Pew Research Center (published July 22, 2025; 68,879 searches from 900 US adults in March 2025) found: "Users who encountered an AI summary clicked on a traditional search result link in 8% of all visits. Those who did not encounter an AI summary clicked on a search result nearly twice as often (15% of visits)"; clicks *inside* the summary were just 1%. A randomized field experiment by researchers at the Indian School of Business and Carnegie Mellon (SSRN working paper, 2025) found AI Overviews cut organic clicks on triggered queries by 38% with no measurable change in user satisfaction. Similarweb data (cited widely) reported zero-click searches rising from 56% to 69% since AI Overviews launched. **Flag:** Google publicly disputes the Pew methodology; exact numbers vary by study, but the direction — fewer clicks reaching publishers — is consistent across independent sources.
- **Forecast (SPECULATED — flag as prediction).** Gartner (press release, Feb 19, 2024): "By 2026, traditional search engine volume will drop 25%, with search marketing losing market share to AI chatbots and other virtual agents" (Alan Antin, VP Analyst). This is a forecast, not an established outcome.
- **Business value signal (CORRELATIONAL/single-vendor).** Multiple vendor studies report AI-referred visitors convert at higher rates than organic — Semrush (June 2025) reported ~4.4x; Ahrefs found AI search was 0.5% of its traffic but drove 12.1% of signups (a 23x conversion rate). **Flag:** these are self-reported vendor analyses of their own traffic with small AI-traffic denominators (AI is still <1% of sessions in most datasets), and attribution is systematically undercounted, so treat specific multipliers with heavy skepticism. The qualitative finding (AI traffic is higher-intent) is more robust than any single multiplier.

### 1.3 Existing players and gaps
Key players as of mid-2026:

- **Profound** — category leader; enterprise focus; SOC 2 Type II; tracks 10+ engines. Its February 2026 press release describes "more than 700 enterprises" including Target, Figma, Walmart, Ramp, MongoDB, Chime and U.S. Bank, serving "more than 10 percent of the Fortune 500." Also publishes large citation studies (680M-citation analysis). Strengths: analytics depth, AI-crawler/agent monitoring (Cloudflare integration). Weakness: enterprise pricing/complexity.
- **Peec AI** — fast-growing mid-market analytics; ~$4M+ ARR in ten months; prompt tracking, competitor gap analysis; ~$95/mo for 50 prompts, unlimited seats.
- **Otterly.ai** — most accessible entry point ($29/mo for 15 prompts); GEO Audit tool with SWOT; tracks ChatGPT, Perplexity, Google AI Overviews, Google AI Mode, Gemini, Copilot. Limited API/export.
- **Scrunch AI** — broad engine coverage including Claude; monitoring-focused.
- **Athena (AthenaHQ), Goodie AI, Evertune, Bluefish, Brandlight, RankPrompt, Rankscale, LLMrefs, Dageno** — a long tail of monitoring/optimization tools. Evertune notably pairs base-model API access with a demographically weighted consumer panel.
- **Legacy SEO suites** — Semrush (AI toolkit / AI Visibility Score) and Ahrefs (Brand Radar) — largest user bases, shallowest AI-specific depth, but strong data assets.

**Gaps and opportunities (where a novel platform/thesis can sit):**
1. **Statistical rigor.** Almost no tool foregrounds confidence intervals, sample sizes, or run-to-run variance. A "measurement-honest" GEO tool is a genuine differentiator and fits the course theme.
2. **Causal attribution, not correlation.** Most tools report "you are/aren't cited." Few run controlled before/after experiments (the Princeton method) to prove a content change *caused* a visibility change.
3. **Action layer.** Profound/Peec/Otterly largely "identify the problem; none execute the solution" (per multiple comparisons). Closing the loop from diagnosis → concrete edit → re-measurement is under-served.
4. **Cross-engine reconciliation.** Since only ~11% of cited domains overlap between ChatGPT and Perplexity (Averi analysis of 680M citations), a tool that normalizes and explains divergence is valuable.

---

## 2. HOW AI ENGINES SELECT & CITE CONTENT

### 2.1 The RAG pipeline (mechanics)
Modern answer engines are two-stage retrieval-augmented generation (RAG) systems: (1) a **retrieval** step fetches candidate documents from an index or live search; (2) a **generation** step (the LLM) synthesizes an answer and emits citations to a subset of retrieved sources. Google describes its own pipeline explicitly: AI features "retrieve relevant pages from the Search index, then generate grounded responses with clickable citations," using **query fan-out** — a single user query is expanded into multiple related sub-queries that each pull results. The Princeton paper modeled exactly this two-step structure (top-5 Google results → GPT-3.5 synthesis at temperature 0.7, five responses per query).

### 2.2 Signals that appear to influence citation — PROVEN vs CORRELATIONAL vs SPECULATED

**PROVEN (controlled experiment — Princeton/KDD 2024).** Over GEO-bench (10,000 queries split 8K/1K/1K train/val/test, drawn from nine datasets — MS MARCO, ORCAS-1, Natural Questions, AllSouls, LIMA, Davinci-Debate, Perplexity.ai Discover, ELI5, and GPT-4-generated queries — spanning 25 domains, distributed 80% informational / 10% transactional / 10% navigational), the authors tested nine content-modification methods against a "No Optimization" baseline, on two metrics they defined:
- **Position-Adjusted Word Count** — the normalized word count of sentences attributed to a source, weighted by an exponentially decaying function of citation position (earlier citations count more), because "sentences that appear first in the response are more likely to be read."
- **Subjective Impression** — an LLM-as-judge (G-Eval/GPT-3.5) score over seven sub-facets: relevance, influence, uniqueness, subjective position, subjective count, click-likelihood, and diversity, normalized to the same mean/variance as Position-Adjusted Word Count.

Results (relative improvement over baseline; Table 1's caption states the best methods improve by **41%** and **28%** on the two metrics respectively):
- **Quotation Addition** (adding quotes from credible sources): top method, ~+41% on Position-Adjusted Word Count (score 27.2 vs 19.3 baseline).
- **Statistics Addition** (replacing qualitative claims with quantitative data): ~+31%, and the strongest Subjective Impression gains.
- **Cite Sources** (adding citations to credible sources): ~+27%.
- **Fluency Optimization** and **Easy-to-Understand**: +15–30%.
- **Authoritative** tone: no significant improvement ("engines are already somewhat robust to such changes").
- **Keyword Stuffing** (classic SEO): **performed WORSE than baseline** (17.7 vs 19.3) — actively harmful.
- Aggregate: the top three (Cite Sources, Quotation Addition, Statistics Addition) achieved 30–40% on Position-Adjusted Word Count and 15–30% on Subjective Impression.
- **"Equalizer effect":** GEO helps low-ranked pages most — Cite Sources gave a **+115.1% visibility increase for the 5th-ranked site** while the top-ranked site's visibility *fell* 30.3% (Table 2). The authors frame this as democratizing the space.
- **Real-world validation on Perplexity.ai (200 queries):** results held — Quotation Addition +22% on Position-Adjusted Word Count; Statistics Addition +37% on Subjective Impression; Keyword Stuffing 10% *worse* than baseline.
- Effects are **domain-specific** (e.g., statistics best for Law/Government/Debate; quotations best for People & Society/History), and combining strategies helps most (Fluency + Statistics beat any single method by >5.5%).

**Limits on the "proof":** the study used GPT-3.5 and a simulated engine circa 2023–24; the 200-query Perplexity test is the only live-engine validation. The "+40%" is a best-case *relative* figure on the authors' own metric, not an average and not a guarantee. Cite it as *"controlled evidence that quotations, statistics, and citations increase AI visibility, with effect sizes of roughly 20–40% in one 2024 study,"* not as a universal law.

**CORRELATIONAL (large aggregators — weaker evidence):**
- **Brand mentions beat backlinks.** Ahrefs' study of 75,000 brands (Aug 2025) found: "Brand web mentions show the strongest correlation (0.664)... Web mentions (0.664) correlate much more strongly than backlinks (0.218)"; the full ranking was branded anchors 0.527, branded search volume 0.392, and domain rating 0.326. A December 2025 follow-up found **YouTube mentions** the single strongest signal (~0.737). Ahrefs itself stresses "correlation ≠ causation" and calls these "moderate to weak" relationships.
- **Structure & factual density.** Ahrefs' billion-datapoint study reportedly found "best of" listicles dominate and that adding schema markup had "almost zero impact" on AI citations, while content structure and factual density mattered more.
- **Off-site presence.** SE Ranking (Nov 2025) found domains with G2/Capterra/Trustpilot profiles had 3x higher ChatGPT citation rates, and strong Reddit/Quora presence 4x. **Flag:** correlational, single-vendor.

**SPECULATED / DEBUNKED (weak or negative evidence):**
- **`llms.txt`:** No strong evidence it improves citations today. Google's May 2026 official guidance explicitly says you do **not** need `llms.txt`, content chunking, AI-specific rewrites, or special schema to appear in its AI features. Kevin Indig: "a good idea that lacks confirmed impact. Adopt it because it's low-cost, not because it's proven."
- **Schema markup as a citation lever:** Google says structured data is not required for AI search. Counter-evidence exists (Semrush reported GPT-4 extraction accuracy jumped from 16% to 54% with schema), so the honest verdict: schema is a "hygiene factor" that helps machine-readability but is not a proven direct citation switch.

### 2.3 How citation behavior differs across engines (documented)
This is the most decision-relevant technical finding: **the engines are not interchangeable.** Analysis of 680M citations found only ~11% of cited domains overlap between ChatGPT and Perplexity; Google AI Overviews and AI Mode cite the same URLs only ~13.7% of the time.

- **ChatGPT Search** — two-layer: static training data + a **Bing-powered** retrieval layer triggered mainly for commercial-intent queries (one study: web search fires 53.5% of the time for commercial vs 18.7% for informational). Leans on authoritative reference sources; Wikipedia is heavily cited (Qwairy's Q3 2025 study of 118,101 answers found ChatGPT averages ~7.92 citations/answer and is the only major model citing Wikipedia significantly, ~4.8%). Strong Bing Webmaster Tools presence helps. On May 7, 2026, ChatGPT began embedding clickable brand links (tagged `utm_source=chatgpt.com`).
- **Perplexity** — real-time web search on **every** query, drawing from multiple search APIs (Google and Bing); no knowledge cutoff; cites content within hours of indexing (one 2026 analysis: 82% of cited content published within 30 days). Highest citation density (~21.87 citations/answer per Qwairy). Historically Reddit-heavy until Reddit sued Perplexity over scraping in October 2025, after which Perplexity's Reddit citations reportedly dropped 86% and YouTube filled the gap.
- **Google AI Overviews / AI Mode (Gemini)** — draws from Google's own organic index via query fan-out, with Gemini as the synthesis engine. E-E-A-T, structure, relevance, and freshness dominate; Moz found 88% of AI Mode citations came from pages outside the organic top 10, and Ahrefs found ~47% of AI Overview citations from pages ranking below position 5 — ranking still helps but is no longer sufficient.
- **Microsoft Copilot** — Bing-index-based, similar to ChatGPT's retrieval layer.
- **Claude** — historically most conservative about web citation; smaller reported referral traffic but reportedly highest conversion (Exposure Ninja, March 2026: Claude 16.8% vs ChatGPT 14.2% vs Perplexity 12.4%). **Flag:** single-vendor.

**Volatility is a first-class finding:** per Profound, Google AI Overviews show 59.3% monthly citation drift, ChatGPT 54.1%, Copilot 53.4%, Perplexity 40.5%. This alone means "point-in-time" GEO scores are unreliable.

---

## 3. PLATFORM ARCHITECTURE

### 3.1 Core components
1. **Prompt/Query Simulation Engine** — manages the prompt set (the "queries you want to win"), paraphrase variants, personas, locales, and scheduling. This is the heart of a GEO platform; the prompt set *is* the measurement instrument.
2. **Engine Connector Layer** — adapters for each answer engine's API (OpenAI Responses `web_search`, Perplexity Sonar, Gemini grounding) plus, where APIs don't exist (AI Overviews as shown to consumers), an optional headless-browser path.
3. **Citation Extraction & Normalization** — parses structured citation annotations (URLs, titles, offsets), resolves and canonicalizes domains, and entity-matches brand mentions in the answer text (regex + NER + LLM-as-judge for fuzzy brand/product references).
4. **Crawler/Ingestion** — fetches the client's own pages and competitor pages for content analysis.
5. **Content Analysis** — scores pages on the *proven* levers (statistic density, quotation/citation presence, heading structure, readability) via deterministic parsers plus LLM-as-judge.
6. **Scoring Engine** — computes visibility metrics (share of voice, citation frequency, average position, sentiment) *with uncertainty*.
7. **Recommendation Engine** — maps gaps to concrete actions grounded in evidence tiers (proven → correlational → experimental).
8. **Dashboard/Reporting & Integrations** — trends, competitor benchmarking, alerts; GA4/Search Console/Looker/Slack integrations; export API.

### 3.2 Reference architecture (data flow, described)
```
[Prompt Set Store] → [Scheduler] → [Engine Connector Layer]
   ├─ OpenAI Responses API (web_search) ┐
   ├─ Perplexity Sonar API              ├─→ [Raw Response Store (JSONB)]
   ├─ Gemini API (Search grounding)     ┘        │
   └─ (optional) Headless browser for AI Overviews
                                                 ↓
                            [Citation Extraction & Normalization]
                                                 ↓
              [Fact Store: (run_id, prompt_id, engine, model, timestamp,
                            cited_url, domain, position, brand_mentioned,
                            sentiment, answer_text_hash)]
                                                 ↓
        ┌────────────────────────────────────────┼──────────────────────────┐
        ↓                                         ↓                          ↓
 [Scoring Engine]                        [Content Analysis] ← [Crawler]  [Recommendation Engine]
 (SoV, freq, position,                   (statistic density,             (evidence-tiered actions)
  variance, CIs)                          quotes, structure)
        └───────────────────────┬────────────────────────────────────────────┘
                                 ↓
                       [Dashboard / Reporting / Alerts / Export API]
```
Data flows one way: prompt scheduling → multi-engine querying → structured citation facts → scoring + content analysis → recommendations → dashboard. The **Fact Store** is append-only (every run is a new immutable row) so variance and drift can be computed historically.

### 3.3 Build vs buy and technical trade-offs
- **Engine APIs vs scraping.** *Use official APIs* for OpenAI, Perplexity (Sonar), and Gemini — they return **structured citation annotations** (OpenAI's `url_citation`, Gemini's `groundingMetadata`, Perplexity's inline citations), are ToS-clean, and are cheap at prototype scale. *Scraping is the trade-off case:* Google **AI Overviews as shown to end users has no official API**, and the Gemini grounding API is *not* identical to consumer AI Overviews. To measure true AI Overviews you must either scrape (ToS risk, brittleness, IP blocks) or accept Gemini grounding as a proxy and document the discrepancy. **Recommendation for a student project: use Gemini grounding as a documented proxy; do not scrape Google.**
- **LLM-as-judge for analysis.** Useful for brand-mention detection, sentiment, and Subjective-Impression-style scoring, but it is itself non-deterministic and biased — pin temperature=0, version-pin the judge model, and validate against a hand-labeled gold set. Report judge agreement (e.g., Cohen's κ against human labels).
- **Vector DB.** Not needed for the tracking MVP. It becomes relevant only if you build a "why did/didn't we get cited" retrieval simulator (embedding client and competitor content). For a 15–20 day project, skip it.
- **Storage.** Postgres with a JSONB column for raw responses is sufficient and ideal — relational for the fact table (queryable for SoV/variance), JSONB for the full raw API payload (so you never lose data as your parser evolves). No warehouse needed at prototype scale.

### 3.4 Data pipeline & schema
Minimum viable schema (Postgres):
- `prompts(prompt_id, text, intent, category, locale, active)`
- `runs(run_id, prompt_id, engine, model, temperature, run_index, ts, raw_response JSONB, answer_text)`
- `citations(citation_id, run_id, cited_url, domain, position, is_target_brand, sentiment)`
- `mentions(mention_id, run_id, entity, is_target_brand, sentiment, char_offset)`
- `content_scores(page_url, crawl_ts, stat_density, quote_count, citation_count, heading_structure_score, readability, has_schema)`

Scale: a solo prototype with 50 prompts × 3 engines × 10 repeats daily ≈ 1,500 API calls/day ≈ 45K rows/month — trivial for Postgres. An enterprise platform tracking thousands of prompts × dozens of models × repeats is where sharding, job queues (Celery/RQ), and cost control matter.

---

## 4. MEASUREMENT & METRICS

### 4.1 Visibility metrics
- **Citation frequency / mention rate** — % of runs (or of a prompt set) in which the target domain/brand appears. The base metric.
- **Share of Voice (SoV)** — target citations ÷ total citations for a prompt set, or target mentions vs competitor mentions. The primary competitive KPI.
- **Position within answer** — rank/order of the citation or first-mention character offset (earlier = more valuable; mirrors the Princeton position-weighting). "Diversity score" (Shannon entropy of cited domains) is a useful supplement.
- **Sentiment** — positive/neutral/negative framing of the brand mention (LLM-as-judge; validate against human labels).
- **Position-Adjusted Word Count / Subjective Impression** — replicate the Princeton definitions directly if you want research-grade metrics.

### 4.2 Tracking methodology at scale
- **Prompt set design** is the core validity question. Build prompts that mirror real buyer/user questions across intents (the Princeton 80/10/10 informational/transactional/navigational split is a reasonable default), include competitor-comparison and category prompts ("best X for Y"), and version them (prompts drift in relevance).
- **Access:** use official APIs with structured citations (Section 5). **Schedule** repeated runs (daily/weekly) to build time series and quantify drift.
- **Sampling:** because outputs are non-deterministic, a single run is not a measurement (see §4.4).

### 4.3 Attribution & ROI
- **Referral traffic:** configure GA4 with a **custom channel group** using regex on referrer domains (`chatgpt.com`, `perplexity.ai`, `gemini.google.com`, etc.). Without this, AI visits fall into Direct/Referral/Unassigned. ChatGPT only began appending `utm_source=chatgpt.com` on desktop in June 2025; mobile/in-app clicks often lack referrers, so **GA4 AI numbers are a floor, not a ceiling.**
- **Downstream:** conversions, signups, revenue attributed to AI-referred sessions; cross-reference rising **branded search volume** in Search Console as a proxy for AI-driven discovery GA4 misattributes to branded organic.
- **ROI caveat:** only ~14–16% of brands track AI search as a distinct channel (late 2025), and AI is still <1% of sessions in most datasets, so ROI models are early and noisy.

### 4.4 Handling non-determinism (the rigor core)
This is where the project should shine. LLM outputs vary run-to-run due to sampling (temperature/top-p) and, even at temperature 0, floating-point non-associativity plus batching/concurrency on GPUs (Thinking Machines / Horace He, 2025). Add live-retrieval variance (the web changes between runs) and the noise compounds.

Concrete methodology:
- **Never report single-run scores.** Run each prompt N times and report mean ± standard deviation and a confidence interval.
- **Sample size & variance decomposition.** A 2026 arXiv study, "Where Does the Noise Come From? A Variance-Components Decomposition of Non-Determinism in LLM Brand Answers" (Zatuchin), applied generalizability theory to 12,933 LLM responses (20 Central/Eastern European brands × 8 languages × 3 models) and decomposed brand-answer variance into four sources — within-prompt resampling, prompt paraphrase, model identity, and query language. Key finding: **adding paraphrases, models, and languages reduces error variance far more per unit cost than repeating the same prompt** — a repeat past the fifth reduces relative-error variance by only ~0.0003, single-answer brand-ranking reliability was ~0.01, and it rose to only ~0.36 even at a fully crossed 8-language × 3-model × 15-paraphrase design. **Design implication: budget your API calls toward paraphrase/model diversity, not many repeats of one prompt.**
- **Bounding controllable variance:** pin model version, set temperature=0 where the goal is measurement stability, pin seed/`system_fingerprint` where supported, and evaluate with **semantic-equivalence** matching (not byte-exact).
- **Report reliability metrics:** treat "is brand X cited" as a Bernoulli trial per run and use a proportion confidence interval (Wilson interval is appropriate for small-n binary data); for share-of-voice use cluster-bootstrap CIs (as the Zatuchin paper does). State explicitly when two brands' visibility is *not* statistically distinguishable.

---

## 5. IMPLEMENTATION ROADMAP (solo, 15–20 days)

### 5.1 Phased plan
**Phase 0 — Scoping & literature (Days 1–3, ~3 days).** Read the Princeton paper (primary source) and 2–3 aggregator studies; lock the project thesis around *measurement honesty*. Deliverable: annotated bibliography + evidence-tier table (proven/correlational/speculated).

**Phase 1 — Research report (Days 3–8, ~4 days, overlaps Phase 0).** Write Sections 1–4 (landscape, mechanics, architecture, metrics).

**Phase 2 — Platform design (Days 8–11, ~3 days).** Produce the architecture, schema, and metric definitions as a design doc + diagram.

**Phase 3 — Prototype ONE component (Days 11–18, ~5–6 days).** Build the cross-engine citation tracker (below).

**Phase 4 — Analysis & write-up (Days 18–20, ~2 days).** Run the tracker, produce a variance/CI analysis, write the "what we learned about reliability" section, list open questions. (Total ~17–18 working days, leaving slack.)

### 5.2 The prototype: a cross-engine citation-tracking harness (highest value, lowest effort)
**Why this one:** it is the atomic, defensible core of every GEO product; it is ToS-clean (official APIs); it produces real data; and it directly enables a computational-skepticism analysis (variance, CIs, cross-engine disagreement).

**Stack:** Python; `openai`, `requests` (Perplexity Sonar), `google-genai` (Gemini); Postgres (or SQLite for simplicity) with SQLAlchemy; pandas + statsmodels + matplotlib for analysis; `.env` for keys.

**Engines & how to get citations:**
- **OpenAI Responses API** with `tools:[{"type":"web_search"}]` — inspect output for `type:"web_search_call"` and `url_citation` annotations (URL, title, char offsets). Cost ~$10/1k tool calls + token/content costs (context-size dependent, up to ~$25–50/1k for large contexts).
- **Perplexity Sonar API** — every call runs a live search and returns citations; Sonar is $1/M tokens in+out (cheapest web-grounded LLM API), Sonar Pro $3/$15 per M; web search included in token price. Best default for a student budget.
- **Gemini API** — enable the `google_search` tool ("Grounding with Google Search"); parse `groundingMetadata` (search queries, web results, citations). Billed per search query on Gemini 3. **Document that this is a proxy for AI Overviews, not identical to them.**
- (Optional stretch) **Claude** with web search tool for a 4th engine.

**Sample query design:** 30–50 prompts across a chosen vertical, split ~80/10/10 informational/commercial/navigational, including 5–10 competitor-comparison prompts ("best [category] tool for [use case]") and 2–3 paraphrases each. Track a chosen target brand + 3–5 competitors.

**Sampling design (the rigor hook):** run each prompt/paraphrase × each engine × **N=5 repeats**, plus a repeat pass on 2–3 different days to capture drift. Prioritize paraphrase/engine breadth over more repeats (per the variance-decomposition finding).

**Data schema:** as in §3.4 (`prompts`, `runs`, `citations`, `mentions`).

**Analysis deliverables:** per-brand citation frequency with Wilson 95% CIs; share-of-voice by engine; cross-engine overlap (replicate the "~11% overlap" finding on your own data); run-to-run variance; and a day-to-day drift chart. The headline student finding will likely be: *"single-run GEO scores are not reproducible; here is how wide the confidence intervals actually are."*

### 5.3 Skills & effort
Solo, technically skilled student. Needed: Python, REST APIs, basic SQL, basic statistics (proportions, bootstrap CIs), and data viz. No ML training required (LLM-as-judge is API-only). Effort per phase given above.

### 5.4 Key risks & mitigations
- **API access/cost limits.** Mitigate: use cheapest tiers (Perplexity Sonar $1/M; Gemini Flash; OpenAI mini-search), cap N, cache raw responses (never re-call for re-analysis). Budget estimate: 50 prompts × 3 paraphrases × 3 engines × 5 repeats × 3 days ≈ 6,750 calls — on the order of tens of dollars, dominated by OpenAI web-search tool fees.
- **ToS / scraping legality.** Mitigate: use official APIs only; do **not** scrape Google AI Overviews or the consumer ChatGPT UI. Note the live litigation backdrop (Reddit v. Perplexity, Oct 2025; publisher suits against Perplexity; Google v. SerpApi) as evidence that scraping AI surfaces carries real legal risk. Document that AI Overviews measurement is proxied via Gemini grounding.
- **Model drift / non-determinism.** Mitigate: version-pin models, timestamp every run, report CIs, and explicitly separate "controllable" variance (sampling) from "environmental" variance (index/model updates). This risk is also the project's central intellectual contribution — frame it as a feature, not a bug.
- **Construct validity.** The prompt set may not reflect real user queries; mitigate by documenting selection criteria and treating results as directional.

---

## Open Questions / Unknowns
1. **Causation vs correlation at scale.** Only the Princeton study is a controlled experiment, and it used GPT-3.5 and a simulated engine. Whether its 20–40% effects hold on 2026 production engines (GPT-5.x, Gemini 3) at scale is **unverified**.
2. **Does `llms.txt`/schema ever help AI citation?** Current evidence is null-to-weak and Google says they're unnecessary — but standards are evolving and agentic/MCP use cases may change this.
3. **True AI Overviews measurement.** There is no sanctioned API for consumer AI Overviews; how well Gemini grounding proxies it is unquantified.
4. **Attribution ground truth.** AI-influenced-but-not-AI-referred journeys (discovery in ChatGPT → later branded search) are structurally invisible to GA4; the real ROI of GEO is therefore under-measured, and the reported conversion multipliers (4.4x, 23x) are unverified beyond single-vendor datasets.
5. **How stable are source preferences?** Reddit's citation share on Perplexity reportedly dropped 86% after one lawsuit; ChatGPT's UGC citations collapsed after late-2025 updates. Engine sourcing can shift discontinuously due to business/legal events, not just algorithms — making long-range GEO strategy inherently uncertain.
6. **Sample sizes for reliability.** The one rigorous variance study covers CEE brands in 8 languages; the right N and design for other verticals/languages is an open empirical question.

---
*Evidence hierarchy for this report: the Princeton/KDD 2024 paper is the only controlled-experiment source and is weighted accordingly; Pew Research and the ISB/CMU field experiment are independent and relatively robust for the zero-click claims; Ahrefs' 75,000-brand study and Profound's 680M-citation analysis are large but observational/correlational and vendor-published; conversion multipliers and single-vendor citation rankings are the weakest tier and are flagged as such throughout.*