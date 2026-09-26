import { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { api, SupporterRow, SupporterDetail } from "../lib/api";
import IntentGauge from "../components/IntentGauge";
import { Search, MapPin, Star, Trophy, PoundSterling, Mail, CheckCircle2, Send } from "lucide-react";

function Stat({ icon, label, value }: { icon: React.ReactNode; label: string; value: string | number }) {
  return (
    <div className="glass-card-light p-3 flex items-center gap-3">
      <div className="text-arsenal-gold">{icon}</div>
      <div>
        <p className="text-[11px] uppercase tracking-wide text-white/50">{label}</p>
        <p className="text-white font-semibold">{value}</p>
      </div>
    </div>
  );
}

export default function Supporter360() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [q, setQ] = useState("");
  const [results, setResults] = useState<SupporterRow[]>([]);
  const [detail, setDetail] = useState<SupporterDetail | null>(null);
  const [activated, setActivated] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api.supporters("", 12).then(setResults).catch(() => {});
  }, []);
  useEffect(() => {
    if (id) {
      api.supporter(id).then(setDetail).catch(() => setDetail(null));
      setActivated(null);
    }
  }, [id]);

  const search = async () => setResults(await api.supporters(q, 15));

  const activate = async () => {
    if (!detail) return;
    setBusy(true);
    try {
      const res = await api.activate({
        supporter_id: detail.profile.supporter_id,
        recommended_action: detail.nba.action,
        selected_action: detail.nba.action,
        campaign: `${detail.nba.opportunity_type} Campaign`,
      });
      setActivated(res.activation_id + " · " + res.store);
    } finally {
      setBusy(false);
    }
  };

  const gbp = (n: number) => "£" + Math.round(n || 0).toLocaleString();

  return (
    <div className="space-y-6">
      <h1 className="font-display text-3xl tracking-wider text-white uppercase">Supporter 360</h1>

      {/* Search */}
      <div className="glass-card p-4 flex gap-3 items-center">
        <Search className="w-5 h-5 text-white/50" />
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && search()}
          placeholder="Search by name or supporter ID (e.g. S000481)…"
          className="flex-1 bg-transparent outline-none text-white placeholder-white/40"
        />
        <button onClick={search} className="px-4 py-2 rounded-lg bg-arsenal-red/25 border border-arsenal-red/40 text-white text-sm hover:bg-arsenal-red/35">
          Search
        </button>
      </div>

      {!id && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
          {results.map((r) => (
            <button
              key={r.supporter_id}
              onClick={() => navigate(`/supporter/${r.supporter_id}`)}
              className="glass-card-light p-4 text-left hover:border-arsenal-red/40 transition"
            >
              <div className="flex justify-between items-start">
                <div>
                  <p className="text-white font-semibold">{r.first_name}</p>
                  <p className="text-xs text-white/50">{r.supporter_id} · {r.country}</p>
                </div>
                <span className="text-2xl font-bold tabular-nums text-arsenal-gold">{r.purchase_intent_score}</span>
              </div>
              <p className="mt-3 text-xs px-2 py-1 rounded bg-white/10 inline-block text-white/80">{r.recommended_action}</p>
              <p className="mt-1 text-[11px] text-white/40">{r.membership_tier}</p>
            </button>
          ))}
        </div>
      )}

      {/* Detail */}
      {id && detail && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Profile + engagement */}
          <div className="lg:col-span-2 space-y-4">
            <div className="glass-card p-6">
              <div className="flex items-center justify-between">
                <div>
                  <h2 className="font-display text-3xl text-white tracking-wide">{detail.profile.first_name}</h2>
                  <p className="text-white/50 text-sm">{detail.profile.supporter_id}</p>
                </div>
                <span className="px-3 py-1 rounded-full bg-arsenal-red/20 border border-arsenal-red/40 text-sm text-white">
                  {detail.profile.membership_tier}
                </span>
              </div>
              <div className="grid grid-cols-2 md:grid-cols-3 gap-3 mt-5">
                <Stat icon={<MapPin className="w-4 h-4" />} label="Location" value={`${detail.profile.city}, ${detail.profile.country}`} />
                <Stat icon={<Star className="w-4 h-4" />} label="Favourite Player" value={detail.profile.favourite_player} />
                <Stat icon={<PoundSterling className="w-4 h-4" />} label="Customer Value" value={gbp(detail.profile.total_customer_value)} />
              </div>
            </div>

            <div className="glass-card p-6">
              <h3 className="font-arsenal-bebas tracking-widest text-white/90 uppercase text-lg mb-4">Engagement</h3>
              <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
                <Stat icon={<Trophy className="w-4 h-4" />} label="Matches Attended" value={detail.profile.matches_attended} />
                <Stat icon={<Ticketish />} label="Ticket Views (30d)" value={detail.profile.ticket_views_30d} />
                <Stat icon={<Search className="w-4 h-4" />} label="Product Views (30d)" value={detail.profile.product_views_30d} />
                <Stat icon={<Mail className="w-4 h-4" />} label="Email Opens (30d)" value={detail.profile.marketing_opens_30d} />
                <Stat icon={<Star className="w-4 h-4" />} label="Membership Views (30d)" value={detail.profile.membership_views_30d} />
                <Stat icon={<PoundSterling className="w-4 h-4" />} label="Days Since Purchase" value={detail.profile.days_since_last_purchase} />
              </div>
            </div>

            {/* Activity timeline */}
            <div className="glass-card p-6">
              <h3 className="font-arsenal-bebas tracking-widest text-white/90 uppercase text-lg mb-4">Recent Activity</h3>
              <div className="space-y-2 max-h-64 overflow-auto pr-2">
                {detail.activity.map((a, i) => (
                  <div key={i} className="flex items-center gap-3 text-sm border-l-2 border-arsenal-gold/40 pl-3 py-1">
                    <span className="text-[10px] uppercase w-20 text-arsenal-gold">{a.channel}</span>
                    <span className="text-white/80 flex-1">{a.activity_type} · {a.activity_detail}</span>
                    <span className="text-white/40 text-xs">{new Date(a.activity_timestamp).toLocaleDateString("en-GB")}</span>
                  </div>
                ))}
                {detail.activity.length === 0 && <p className="text-white/40 text-sm">No recent activity.</p>}
              </div>
            </div>
          </div>

          {/* Intent + NBA */}
          <div className="space-y-4">
            <div className="glass-card p-6 flex flex-col items-center">
              <h3 className="font-arsenal-bebas tracking-widest text-white/90 uppercase text-lg mb-4">Purchase Intent</h3>
              <IntentGauge score={detail.intent} />
              <p className="text-white/50 text-xs mt-3">Engagement score: {detail.engagement}/100</p>
            </div>

            <div className="glass-card p-6 border-arsenal-red/30">
              <p className="text-xs uppercase tracking-widest text-arsenal-gold">Next Best Action</p>
              <h3 className="font-display text-2xl text-white mt-1 mb-3">{detail.nba.action}</h3>
              <p className="text-white/75 text-sm leading-relaxed italic">“{detail.nba.reason}”</p>

              <button
                onClick={activate}
                disabled={busy || !!activated}
                className="mt-5 w-full inline-flex items-center justify-center gap-2 px-4 py-3 rounded-lg bg-arsenal-red text-white font-semibold hover:bg-arsenal-red-dark disabled:opacity-60 transition"
              >
                {activated ? <CheckCircle2 className="w-4 h-4" /> : <Send className="w-4 h-4" />}
                {activated ? "Added to Campaign" : busy ? "Writing to Lakebase…" : "Add to Campaign"}
              </button>
              {activated && (
                <p className="mt-2 text-xs text-emerald-300 text-center">
                  Activation written · {activated}
                </p>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function Ticketish() {
  return <span className="inline-block w-4 h-4">🎟️</span>;
}
