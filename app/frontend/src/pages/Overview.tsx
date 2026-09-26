import { useEffect, useState } from "react";
import { api, Overview as OverviewData } from "../lib/api";
import KPITile from "../components/KPITile";
import { Users, Flame, PoundSterling, Ticket, Target } from "lucide-react";
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

export default function Overview() {
  const [d, setD] = useState<OverviewData | null>(null);
  const [err, setErr] = useState("");

  useEffect(() => {
    api.overview().then(setD).catch((e) => setErr(String(e)));
  }, []);

  if (err) return <div className="text-rose-300">Failed to load overview: {err}</div>;
  if (!d) return <div className="text-white/60 animate-pulse-live">Loading Arsenal Fan 360…</div>;

  const gbp = (n: number) => "£" + Math.round(n).toLocaleString();

  return (
    <div className="space-y-6">
      <div>
        <h1 className="font-display text-4xl tracking-wider text-white uppercase">Arsenal Fan 360</h1>
        <p className="text-white/60 mt-1">
          Turn supporter signals into the next best action ·{" "}
          <span className="text-arsenal-gold">{d.data_source}</span>
        </p>
      </div>

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
