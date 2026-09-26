const API = "/api";

async function get<T>(path: string): Promise<T> {
  const r = await fetch(`${API}${path}`);
  if (!r.ok) throw new Error(`API ${r.status}`);
  return r.json();
}
async function post<T>(path: string, body: unknown): Promise<T> {
  const r = await fetch(`${API}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error(`API ${r.status}`);
  return r.json();
}

export interface Overview {
  kpis: {
    total_supporters: number;
    high_intent: number;
    revenue: number;
    matches_attended: number;
    open_opportunities: number;
  };
  intent_distribution: { band: string; count: number }[];
  actions: { action: string; count: number }[];
  revenue_by_segment: { segment: string; value: number }[];
  engagement_trend: { label: string; score: number }[];
  data_source: string;
}

export interface SupporterRow {
  supporter_id: string;
  first_name: string;
  membership_tier: string;
  country: string;
  purchase_intent_score: number;
  recommended_action: string;
}

export interface SupporterDetail {
  profile: Record<string, any>;
  intent: number;
  engagement: number;
  nba: { action: string; reason: string; opportunity_type: string };
  activity: { channel: string; activity_type: string; activity_detail: string; activity_timestamp: string }[];
}

export interface Opportunity {
  type: string;
  count: number;
  description: string;
  action: string;
}

export const api = {
  overview: () => get<Overview>("/overview"),
  supporters: (q = "", limit = 25) =>
    get<SupporterRow[]>(`/supporters?q=${encodeURIComponent(q)}&limit=${limit}`),
  supporter: (id: string) => get<SupporterDetail>(`/supporter/${id}`),
  opportunities: () => get<Opportunity[]>("/opportunities"),
  opportunitySupporters: (type: string) =>
    get<SupporterRow[]>(`/opportunities/${encodeURIComponent(type)}/supporters`),
  activate: (body: { supporter_id: string; recommended_action: string; selected_action: string; campaign: string }) =>
    post<{ activation_id: string; status: string; store: string }>("/activation", body),
  activations: () => get<any[]>("/activations"),
  genieSuggestions: () => get<{ questions: string[] }>("/genie/suggestions"),
  genieAsk: (question: string) => post<{ answer: string; source: string; rows?: any[] }>("/genie/ask", { question }),
  health: () => get<Record<string, unknown>>("/health"),
};
