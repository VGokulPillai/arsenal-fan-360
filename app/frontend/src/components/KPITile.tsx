import { ReactNode } from "react";

interface Props {
  title: string;
  value: string | number;
  subtitle?: string;
  icon?: ReactNode;
}

export default function KPITile({ title, value, subtitle, icon }: Props) {
  return (
    <div className="glass-card-light h-full w-full min-h-[7.5rem] p-4 sm:p-5 flex flex-col">
      <div className="flex items-start justify-between gap-2 flex-1 min-h-0">
        <div className="min-w-0 flex-1 flex flex-col">
          <p className="text-xs text-white/60 font-medium uppercase tracking-wide leading-snug">
            {title}
          </p>
          <p className="text-3xl font-bold text-white mt-2 leading-none tabular-nums shrink-0">
            {value}
          </p>
          {subtitle && <p className="text-xs text-white/50 mt-2 leading-snug">{subtitle}</p>}
        </div>
        {icon && <div className="p-2 rounded-lg bg-arsenal-red/20 text-arsenal-gold shrink-0">{icon}</div>}
      </div>
    </div>
  );
}
