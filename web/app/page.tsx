"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import type { BrandProfile } from "@/lib/types";

const FALLBACK_ENGINES = ["openai", "perplexity", "gemini", "anthropic"];

function splitCsv(s: string): string[] {
  return s
    .split(",")
    .map((x) => x.trim())
    .filter(Boolean);
}

export default function NewAnalysisPage() {
  const router = useRouter();

  const [knownEngines, setKnownEngines] = useState<string[]>(FALLBACK_ENGINES);
  const [brands, setBrands] = useState<BrandProfile[]>([]);
  const [healthError, setHealthError] = useState<string | null>(null);

  const [brand, setBrand] = useState("");
  const [category, setCategory] = useState("");
  const [aliases, setAliases] = useState("");
  const [competitors, setCompetitors] = useState("");
  const [targetDomain, setTargetDomain] = useState("");
  const [competitorDomains, setCompetitorDomains] = useState("");
  const [engines, setEngines] = useState<string[]>(FALLBACK_ENGINES);
  const [nPrompts, setNPrompts] = useState(30);
  const [repeats, setRepeats] = useState(5);
  const [mode, setMode] = useState<"dry-run" | "live">("dry-run");
  const [saveBrand, setSaveBrand] = useState(false);

  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Load engine list from /health and any saved brand profiles (both best-effort).
  useEffect(() => {
    api
      .health()
      .then((h) => {
        if (h.known_engines?.length) {
          setKnownEngines(h.known_engines);
          setEngines(h.known_engines);
        }
      })
      .catch((e: Error) => setHealthError(e.message));
    api
      .listBrands()
      .then(setBrands)
      .catch(() => {
        /* brand prefill is a nice-to-have; ignore failures */
      });
  }, []);

  function toggleEngine(e: string) {
    setEngines((prev) =>
      prev.includes(e) ? prev.filter((x) => x !== e) : [...prev, e],
    );
  }

  function prefillFromBrand(id: string) {
    if (!id) return;
    const b = brands.find((x) => String(x.id) === id);
    if (!b) return;
    setBrand(b.name);
    setCategory(b.category);
    setTargetDomain(b.domain || "");
    setAliases((b.aliases || []).join(", "));
    setCompetitors((b.competitors || []).join(", "));
    setCompetitorDomains((b.competitor_domains || []).join(", "));
  }

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);

    if (!brand.trim() || !category.trim()) {
      setError("Brand and category are required.");
      return;
    }
    if (engines.length === 0) {
      setError("Select at least one engine.");
      return;
    }

    setSubmitting(true);
    try {
      const created = await api.createRun({
        brand: brand.trim(),
        category: category.trim(),
        aliases: splitCsv(aliases),
        competitors: splitCsv(competitors),
        target_domain: targetDomain.trim() || null,
        competitor_domains: splitCsv(competitorDomains),
        engines,
        n_prompts: nPrompts,
        repeats,
        mode: "dry-run", // live is gated server-side; UI never submits live
        locale: "us",
        seed: 0,
        save_brand: saveBrand,
      });
      router.push(`/runs/${created.run.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      setSubmitting(false);
    }
  }

  return (
    <main className="container">
      <h1>New Analysis</h1>
      <p className="subtitle">
        Run a measurement-honest GEO analysis. Every rate is reported with a
        confidence interval — no bare visibility scores.
      </p>

      {healthError && (
        <div className="banner error">
          <div className="big">API unreachable</div>
          <div className="sub">
            {healthError} Using default engine list; a dry-run submit will fail
            until the backend is up.
          </div>
        </div>
      )}

      <form onSubmit={onSubmit}>
        {brands.length > 0 && (
          <div className="card">
            <div className="field" style={{ marginBottom: 0 }}>
              <label htmlFor="brand-prefill">Prefill from a saved brand</label>
              <select
                id="brand-prefill"
                defaultValue=""
                onChange={(e) => prefillFromBrand(e.target.value)}
              >
                <option value="">— none —</option>
                {brands.map((b) => (
                  <option key={b.id} value={String(b.id)}>
                    {b.name} ({b.category})
                  </option>
                ))}
              </select>
            </div>
          </div>
        )}

        <div className="card">
          <h2>Brand</h2>
          <div className="hint">What are we measuring visibility for?</div>

          <div className="grid-2">
            <div className="field">
              <label htmlFor="brand">Brand *</label>
              <input
                id="brand"
                type="text"
                value={brand}
                onChange={(e) => setBrand(e.target.value)}
                placeholder="e.g. Asana"
                required
              />
            </div>
            <div className="field">
              <label htmlFor="category">Category *</label>
              <input
                id="category"
                type="text"
                value={category}
                onChange={(e) => setCategory(e.target.value)}
                placeholder="e.g. project management software"
                required
              />
            </div>
          </div>

          <div className="field">
            <label htmlFor="aliases">Aliases</label>
            <div className="desc">Comma-separated alternate names.</div>
            <input
              id="aliases"
              type="text"
              value={aliases}
              onChange={(e) => setAliases(e.target.value)}
              placeholder="Asana Inc, asana.com"
            />
          </div>

          <div className="field">
            <label htmlFor="target-domain">Target domain</label>
            <input
              id="target-domain"
              type="text"
              value={targetDomain}
              onChange={(e) => setTargetDomain(e.target.value)}
              placeholder="asana.com"
            />
          </div>
        </div>

        <div className="card">
          <h2>Competitors</h2>
          <div className="hint">Used for share-of-voice comparison.</div>
          <div className="field">
            <label htmlFor="competitors">Competitors</label>
            <div className="desc">Comma-separated brand names.</div>
            <input
              id="competitors"
              type="text"
              value={competitors}
              onChange={(e) => setCompetitors(e.target.value)}
              placeholder="Monday.com, Trello, ClickUp"
            />
          </div>
          <div className="field">
            <label htmlFor="competitor-domains">Competitor domains</label>
            <div className="desc">Comma-separated domains.</div>
            <input
              id="competitor-domains"
              type="text"
              value={competitorDomains}
              onChange={(e) => setCompetitorDomains(e.target.value)}
              placeholder="monday.com, trello.com, clickup.com"
            />
          </div>
        </div>

        <div className="card">
          <h2>Engines</h2>
          <div className="hint">
            Generative engines to query. Defaults to all known engines.
          </div>
          <div className="checks">
            {knownEngines.map((e) => (
              <label key={e} className="check">
                <input
                  type="checkbox"
                  checked={engines.includes(e)}
                  onChange={() => toggleEngine(e)}
                />
                {e}
              </label>
            ))}
          </div>
        </div>

        <div className="card">
          <h2>Sampling</h2>
          <div className="hint">
            Prompts × repeats determines the sample size behind each confidence
            interval.
          </div>
          <div className="grid-2">
            <div className="field">
              <label htmlFor="n-prompts">Prompts (1–100)</label>
              <input
                id="n-prompts"
                type="number"
                min={1}
                max={100}
                value={nPrompts}
                onChange={(e) =>
                  setNPrompts(Math.max(1, Math.min(100, Number(e.target.value))))
                }
              />
            </div>
            <div className="field">
              <label htmlFor="repeats">Repeats (1–20)</label>
              <input
                id="repeats"
                type="number"
                min={1}
                max={20}
                value={repeats}
                onChange={(e) =>
                  setRepeats(Math.max(1, Math.min(20, Number(e.target.value))))
                }
              />
            </div>
          </div>
        </div>

        <div className="card">
          <h2>Mode</h2>
          <div className="hint">
            Dry-run is synthetic, offline, and free. Live runs are gated in this
            build.
          </div>
          <div className="toggle">
            <button
              type="button"
              className={mode === "dry-run" ? "on" : ""}
              onClick={() => setMode("dry-run")}
            >
              Dry-run (synthetic, $0)
            </button>
            <button type="button" disabled title="Live is disabled in this build">
              Live (disabled)
            </button>
          </div>
          <div className="note">
            Live runs spend real money — use the CLI in this build.
          </div>

          <label className="check" style={{ marginTop: 16 }}>
            <input
              type="checkbox"
              checked={saveBrand}
              onChange={(e) => setSaveBrand(e.target.checked)}
            />
            Save this brand profile for reuse
          </label>
        </div>

        {error && (
          <div className="banner error">
            <div className="big">Could not start the run</div>
            <div className="sub">{error}</div>
          </div>
        )}

        <button type="submit" className="primary" disabled={submitting}>
          {submitting && <span className="spinner" />}
          {submitting ? "Running dry-run analysis…" : "Run dry-run analysis"}
        </button>
      </form>
    </main>
  );
}
