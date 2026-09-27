import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, Opportunity, SupporterRow } from "../lib/api";
import { Ticket, Star, ShoppingBag, Crown, HeartPulse, MapPin } from "lucide-react";

const ICONS: Record<string, React.ReactNode> = {
  "Ticket Intent": <Ticket className="w-6 h-6" />,
  "Membership Opportunity": <Star className="w-6 h-6" />,
  "Merchandise Opportunity": <ShoppingBag className="w-6 h-6" />,
  "Hospitality Opportunity": <Crown className="w-6 h-6" />,
  "Re-engagement": <HeartPulse className="w-6 h-6" />,
  Experience: <MapPin className="w-6 h-6" />,
};

export default function Opportunities() {
  const [opps, setOpps] = useState<Opportunity[]>([]);
  const [active, setActive] = useState<string | null>(null);
  const [rows, setRows] = useState<SupporterRow[]>([]);
  const navigate = useNavigate();

  useEffect(() => {
    api.opportunities().then(setOpps).catch(() => {});
  }, []);

  const drill = async (type: string) => {
    setActive(type);
    setRows(await api.opportunitySupporters(type));
  };

  return (
    <div className="space-y-6">
      <h1 className="font-display text-3xl tracking-wider text-white uppercase">Commercial Opportunities</h1>
      <p className="text-white/60 -mt-2">The biggest activation opportunities right now, ranked by supporters in each cohort.</p>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {opps.map((o) => (
          <button
            key={o.type}
            onClick={() => drill(o.type)}
            className={`glass-card p-6 text-left transition hover:-translate-y-1 ${active === o.type ? "border-arsenal-red/50" : ""}`}
          >
            <div className="flex items-center justify-between">
              <div className="p-2 rounded-lg bg-arsenal-red/20 text-arsenal-gold">{ICONS[o.type] || <Star className="w-6 h-6" />}</div>
              <span className="text-3xl font-bold text-white tabular-nums">{o.count.toLocaleString()}</span>
            </div>
            <h3 className="font-display text-xl text-white mt-4 tracking-wide">{o.type}</h3>
            <p className="text-white/60 text-sm mt-1">{o.description}</p>
            <div className="grid grid-cols-2 gap-2 mt-3">
              <div className="rounded-md bg-white/[0.04] px-2 py-1">
                <div className="text-white/40 text-[10px] uppercase tracking-wide">Cohort value</div>
                <div className="text-white text-sm font-semibold">£{o.value.toLocaleString()}</div>
              </div>
              <div className="rounded-md bg-white/[0.04] px-2 py-1">
                <div className="text-white/40 text-[10px] uppercase tracking-wide">Avg intent</div>
                <div className="text-white text-sm font-semibold">{o.avg_intent}</div>
              </div>
            </div>
            <p className="text-arsenal-gold text-xs mt-3 uppercase tracking-wide">→ {o.action}</p>
            <p className="text-white/40 text-[11px] mt-2">Owner: {o.owner} · KPI: {o.kpi}</p>
          </button>
        ))}
      </div>

      {active && (
        <div className="glass-card p-6">
          <h3 className="font-arsenal-bebas tracking-widest text-white/90 uppercase text-lg mb-4">
            {active} — {rows.length} supporters
          </h3>
          <div className="overflow-auto max-h-[26rem]">
            <table className="w-full text-sm">
              <thead className="text-white/50 text-left border-b border-white/10">
                <tr>
                  <th className="py-2">Supporter</th><th>ID</th><th>Tier</th><th>Country</th><th className="text-right">Intent</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.supporter_id} className="border-b border-white/5 hover:bg-white/5 cursor-pointer"
                      onClick={() => navigate(`/supporter/${r.supporter_id}`)}>
                    <td className="py-2 text-white">{r.first_name}</td>
                    <td className="text-white/60">{r.supporter_id}</td>
                    <td className="text-white/60">{r.membership_tier}</td>
                    <td className="text-white/60">{r.country}</td>
                    <td className="text-right font-semibold text-arsenal-gold">{r.purchase_intent_score}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
