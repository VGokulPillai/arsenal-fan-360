import { useEffect, useState } from "react";
import { api, Overview as OverviewData, Executive } from "../lib/api";
import KPITile from "../components/KPITile";
import { Users, Flame, PoundSterling, Ticket, Target, Briefcase, UserCog, TrendingUp } from "lucide-react";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell,
  PieChart, Pie, LineChart, Line, CartesianGrid,
} from "recharts";

const RED = "#EF0107";
const GOLD = "#C5A55A";
const NAVY = "#4f7fc0";
const PIE = [RED, GOLD, NAVY, "#8b5cf6", "#10b981", "#94a3b8"];

function Panel({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="glass-card p-5">
      <h3 className="font-arsenal-bebas tracking-widest text-white/90 uppercase text-lg mb-4">{title}</h3>
      {children}
    </div>
  );
}

function PersonaCard({ icon, kind, role, pressures }: { icon: React.ReactNode; kind: string; role: string; pressures: string[] }) {
  return (
    <div className="rounded-xl border border-white/10 bg-white/[0.03] p-4">
      <div className="flex items-center gap-2 text-arsenal-gold">
        {icon}
        <span className="text-xs uppercase tracking-widest text-white/50">{kind}</span>
      </div>
      <div className="text-white font-semibold text-lg mt-1">{role}</div>
      <ul className="mt-2 space-y-1">
        {pressures.slice(0, 6).map((p) => (
          <li key={p} className="text-white/70 text-sm flex gap-2"><span className="text-arsenal-red">•</span>{p}</li>
        ))}
      </ul>
    </div>
  );
}

export default function Overview() {
  const [d, setD] = useState<OverviewData | null>(null);
  const [ex, setEx] = useState<Executive | null>(null);
  const [err, setErr] = useState("");

  useEffect(() => {
    api.overview().then(setD).catch((e) => setErr(String(e)));
    api.executive().then(setEx).catch(() => {});
  }, []);

  if (err) return <div className="text-rose-300">Failed to load overview: {err}</div>;
  if (!d) return <div className="text-white/60 animate-pulse-live">Loading Arsenal Fan 360…</div>;

  const gbp = (n: number) => "£" + Math.round(n).toLocaleString();

  return (
    <div className="space-y-6">
      <div>
        <h1 className="font-display text-4xl tracking-wider text-white uppercase">Arsenal Fan 360</h1>
        <p className="text-white/60 mt-1">
          Commercial Command Centre · turn supporter signals into the next best action ·{" "}
          <span className="text-arsenal-gold">{d.data_source}</span>
        </p>
      </div>

      {ex && (
        <div className="glass-card p-5 space-y-5">
          <h3 className="font-arsenal-bebas tracking-widest text-white/90 uppercase text-lg">Executive Lens</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <PersonaCard icon={<Briefcase className="w-4 h-4" />} kind={ex.personas.economic_buyer.kind}
              role={ex.personas.economic_buyer.role} pressures={ex.personas.economic_buyer.pressures} />
            <PersonaCard icon={<UserCog className="w-4 h-4" />} kind={ex.personas.operational_owner.kind}
              role={ex.personas.operational_owner.role} pressures={ex.personas.operational_owner.pressures} />
          </div>

          <div>
            <div className="text-xs uppercase tracking-widest text-white/50 mb-2">Commercial KPIs</div>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <KPITile title="Total Supporter Value" value={gbp(ex.commercial_kpis.total_supporter_value)} icon={<PoundSterling className="w-5 h-5" />} />
              <KPITile title="High-Intent Supporters" value={ex.commercial_kpis.high_intent_supporters.toLocaleString()} subtitle="intent ≥ 70" icon={<Flame className="w-5 h-5" />} />
              <KPITile title="High-Intent Value" value={gbp(ex.commercial_kpis.high_intent_value)} icon={<TrendingUp className="w-5 h-5" />} />
              <KPITile title="Membership Opportunity" value={gbp(ex.commercial_kpis.membership_opportunity.value)} subtitle={`${ex.commercial_kpis.membership_opportunity.count} supporters`} icon={<Target className="w-5 h-5" />} />
            </div>
          </div>

          <div>
            <div className="text-xs uppercase tracking-widest text-white/50 mb-2">Commercial Opportunities</div>
            <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
              {([
                ["Ticket Intent", ex.commercial_kpis.ticket_intent],
                ["Membership", ex.commercial_kpis.membership_opportunity],
                ["Merchandise", ex.commercial_kpis.merchandise_opportunity],
                ["Hospitality", ex.commercial_kpis.hospitality_opportunity],
                ["Re-engagement", ex.commercial_kpis.reengagement_opportunity],
              ] as const).map(([label, m]) => (
                <div key={label} className="rounded-lg border border-white/10 bg-white/[0.03] p-3">
                  <div className="text-white/80 text-sm font-semibold">{label}</div>
                  <div className="text-white text-lg">{gbp(m.value)}</div>
                  <div className="text-white/50 text-xs">{m.count} supporters · avg intent {m.avg_intent}</div>
                </div>
              ))}
            </div>
          </div>

          <div className="rounded-xl border border-arsenal-gold/30 bg-arsenal-gold/[0.05] p-4">
            <div className="flex items-center gap-2 text-arsenal-gold">
              <TrendingUp className="w-4 h-4" />
              <span className="text-xs uppercase tracking-widest">Illustrative Business Case</span>
            </div>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mt-3">
              <div><div className="text-white/50 text-xs">Incremental Contribution</div><div className="text-white text-xl font-semibold">{gbp(ex.business_case.illustrative_results.incremental_gross_contribution)}</div></div>
              <div><div className="text-white/50 text-xs">ROI</div><div className="text-white text-xl font-semibold">{ex.business_case.illustrative_results.roi_x}× ({ex.business_case.illustrative_results.roi_pct}%)</div></div>
              <div><div className="text-white/50 text-xs">Payback</div><div className="text-white text-xl font-semibold">{ex.business_case.illustrative_results.payback_months ?? "—"} mo</div></div>
              <div><div className="text-white/50 text-xs">Scaled Addressable</div><div className="text-white text-xl font-semibold">{gbp(ex.business_case.illustrative_results.scaled_addressable_value)}</div></div>
            </div>
            <p className="text-white/40 text-xs mt-3 italic">{ex.business_case.disclaimer}</p>
          </div>
        </div>
      )}

      <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
        <KPITile title="Total Supporters" value={d.kpis.total_supporters.toLocaleString()} icon={<Users className="w-5 h-5" />} />
        <KPITile title="High Intent" value={d.kpis.high_intent.toLocaleString()} subtitle="intent ≥ 70" icon={<Flame className="w-5 h-5" />} />
        <KPITile title="Revenue" value={gbp(d.kpis.revenue)} subtitle="ticket + merch" icon={<PoundSterling className="w-5 h-5" />} />
        <KPITile title="Match Attendance" value={d.kpis.matches_attended.toLocaleString()} icon={<Ticket className="w-5 h-5" />} />
        <KPITile title="Open Opportunities" value={d.kpis.open_opportunities.toLocaleString()} icon={<Target className="w-5 h-5" />} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Panel title="Purchase Intent Distribution">
          <ResponsiveContainer width="100%" height={240}>
            <BarChart data={d.intent_distribution}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.08)" />
              <XAxis dataKey="band" tick={{ fill: "#cbd5e1", fontSize: 12 }} />
              <YAxis tick={{ fill: "#cbd5e1", fontSize: 12 }} />
              <Tooltip contentStyle={{ background: "#111", border: "1px solid #333", borderRadius: 8 }} />
              <Bar dataKey="count" radius={[6, 6, 0, 0]}>
                {d.intent_distribution.map((_, i) => <Cell key={i} fill={[NAVY, GOLD, RED][i] || RED} />)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </Panel>

        <Panel title="Recommended Next Best Action">
          <ResponsiveContainer width="100%" height={240}>
            <PieChart>
              <Pie data={d.actions} dataKey="count" nameKey="action" cx="50%" cy="50%" outerRadius={90} label={(e) => e.action}>
                {d.actions.map((_, i) => <Cell key={i} fill={PIE[i % PIE.length]} />)}
              </Pie>
              <Tooltip contentStyle={{ background: "#111", border: "1px solid #333", borderRadius: 8 }} />
            </PieChart>
          </ResponsiveContainer>
        </Panel>

        <Panel title="Revenue by Supporter Segment">
          <ResponsiveContainer width="100%" height={240}>
            <BarChart data={d.revenue_by_segment} layout="vertical">
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.08)" />
              <XAxis type="number" tick={{ fill: "#cbd5e1", fontSize: 12 }} />
              <YAxis type="category" dataKey="segment" width={90} tick={{ fill: "#cbd5e1", fontSize: 12 }} />
              <Tooltip contentStyle={{ background: "#111", border: "1px solid #333", borderRadius: 8 }} formatter={(v: number) => gbp(v)} />
              <Bar dataKey="value" radius={[0, 6, 6, 0]}>
                {d.revenue_by_segment.map((_, i) => <Cell key={i} fill={i === 0 ? RED : GOLD} />)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </Panel>

        <Panel title="Engagement Trend">
          <ResponsiveContainer width="100%" height={240}>
            <LineChart data={d.engagement_trend}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.08)" />
              <XAxis dataKey="label" tick={{ fill: "#cbd5e1", fontSize: 12 }} />
              <YAxis tick={{ fill: "#cbd5e1", fontSize: 12 }} />
              <Tooltip contentStyle={{ background: "#111", border: "1px solid #333", borderRadius: 8 }} />
              <Line type="monotone" dataKey="score" stroke={RED} strokeWidth={3} dot={{ fill: GOLD }} />
            </LineChart>
          </ResponsiveContainer>
        </Panel>
      </div>
    </div>
  );
}
