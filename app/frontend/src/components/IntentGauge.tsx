interface Props {
  score: number;
  size?: number;
}

// Circular intent-score indicator (0-100) with Arsenal-red gradient.
export default function IntentGauge({ score, size = 150 }: Props) {
  const r = size / 2 - 12;
  const c = 2 * Math.PI * r;
  const pct = Math.max(0, Math.min(100, score));
  const offset = c - (pct / 100) * c;
  const color = pct >= 70 ? "#EF0107" : pct >= 40 ? "#C5A55A" : "#6b7280";
  const label = pct >= 70 ? "HIGH INTENT" : pct >= 40 ? "MEDIUM" : "LOW";

  return (
    <div className="relative inline-flex items-center justify-center" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90">
        <circle cx={size / 2} cy={size / 2} r={r} stroke="rgba(255,255,255,0.12)" strokeWidth="12" fill="none" />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          stroke={color}
          strokeWidth="12"
          fill="none"
          strokeLinecap="round"
          strokeDasharray={c}
          strokeDashoffset={offset}
          style={{ transition: "stroke-dashoffset 0.9s cubic-bezier(0.22,1,0.36,1)" }}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="text-4xl font-bold text-white tabular-nums leading-none">{pct}</span>
        <span className="text-[10px] tracking-widest mt-1" style={{ color }}>{label}</span>
      </div>
    </div>
  );
}
