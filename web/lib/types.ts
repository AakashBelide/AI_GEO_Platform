// Shared types mirroring the AI_GEO FastAPI contract.
// Kept intentionally permissive: reports evolve, so optional/loose fields are the norm.

export interface HealthResponse {
  ok: boolean;
  engines: Record<string, boolean>;
  known_engines: string[];
}

export interface RunSummary {
  id: number;
  brand: string;
  category: string;
  mode: string;
  status: string;
  progress_pct: number;
  actual_cost: number;
  created_at: string | null;
  finished_at: string | null;
}

export interface RunDetail extends RunSummary {
  error: string | null;
}

export interface RunRequest {
  brand: string;
  category: string;
  aliases: string[];
  competitors: string[];
  target_domain?: string | null;
  competitor_domains: string[];
  engines: string[];
  n_prompts: number;
  repeats: number;
  mode: "dry-run" | "live";
  locale?: string;
  seed?: number;
  save_brand?: boolean;
}

export interface RunCreated {
  run: RunDetail;
  report: GeoReport | null;
}

export interface BrandProfile {
  id?: number;
  name: string;
  category: string;
  domain?: string | null;
  aliases?: string[];
  competitors?: string[];
  competitor_domains?: string[];
}

// --- GeoReport shape (render defensively; fields may be missing on older reports) ---

export interface Interval {
  point: number;
  lo: number;
  hi: number;
  n: number;
  confidence?: number;
}

export interface PositionMetric {
  n_cited: number;
  mean_rank: number | null;
  mean_first_offset: number | null;
}

export interface EngineMetrics {
  n_runs: number;
  mention?: Interval;
  citation?: Interval;
  share_of_voice?: Interval;
  position?: PositionMetric;
}

export interface PromptSetIntent {
  count: number;
  fraction: number;
}

export interface PromptSet {
  count: number;
  intents?: Record<string, PromptSetIntent>;
  skew?: { ok?: boolean; message?: string; [k: string]: unknown };
}

export interface Citation {
  url: string;
  domain: string;
  position?: number;
}

export interface TranscriptSample {
  prompt_text: string;
  answer: string;
  citations?: Citation[];
}

export interface Prompt {
  text: string;
  intent?: string;
  category?: string;
}

export interface Reconciliation {
  overlap?: {
    mean_pairwise_jaccard?: number;
    per_engine_unique_domains?: Record<string, number>;
    pairwise_jaccard?: Record<string, number>;
    n_engines?: number;
  };
  divergence?: Array<{ engine: string; ecosystem: string; delta: number }>;
  methodology?: { caveats?: string[]; [k: string]: unknown };
  [k: string]: unknown;
}

export interface GeoReport {
  brand: string;
  category: string;
  mode: string;
  generated_utc: string;
  prompt_set: PromptSet;
  per_engine_metrics: Record<string, EngineMetrics>;
  reconciliation: Reconciliation;
  spend?: Record<string, unknown>;
  notes?: string[];
  prompts?: Prompt[];
  transcript?: Record<string, TranscriptSample[]>;
  top_domains?: Record<string, Array<[string, number]>>;
  findings?: string[];
  recommendations?: string[];
  target_domain?: string | null;
}
