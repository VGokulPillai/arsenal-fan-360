import { ReactNode } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import crestImg from "../assets/arsenal-crest.png";
import { LayoutDashboard, UserSearch, Target, Sparkles } from "lucide-react";

const navItems = [
  { path: "/", label: "Overview", icon: LayoutDashboard },
  { path: "/supporter", label: "Supporter 360", icon: UserSearch },
  { path: "/opportunities", label: "Opportunities", icon: Target },
  { path: "/ask", label: "Ask Arsenal", icon: Sparkles },
];

export default function Layout({ children }: { children: ReactNode }) {
  const location = useLocation();
  const navigate = useNavigate();

  return (
    <div className="min-h-screen flex relative isolate overflow-hidden">
      {/* Emirates Stadium hero background */}
      <div
        className="fixed inset-0 z-0 pointer-events-none animate-ken-burns"
        style={{
          backgroundImage: "url(/images/emirates-banner.png)",
          backgroundSize: "cover",
          backgroundPosition: "center 42%",
          backgroundRepeat: "no-repeat",
        }}
        aria-hidden
      />
      <div
        className="fixed inset-0 z-[1] pointer-events-none"
        style={{
          background: `
            radial-gradient(ellipse 120% 80% at 50% 10%, rgba(239, 1, 7, 0.15) 0%, transparent 60%),
            linear-gradient(180deg,
              rgba(5, 5, 15, 0.72) 0%, rgba(5, 5, 15, 0.48) 15%,
              rgba(10, 10, 20, 0.38) 40%, rgba(10, 10, 20, 0.58) 70%,
              rgba(5, 5, 15, 0.82) 100%)`,
        }}
        aria-hidden
      />

      {/* Sidebar */}
      <aside className="relative z-10 w-64 flex flex-col border-r border-white/15 bg-black/40 backdrop-blur-2xl">
        <div className="p-3 border-b border-white/10">
          <div className="flex items-center gap-2 text-xs text-arsenal-gold">
            <img src="/images/databricks-logo.png" alt="" className="h-8 w-8 shrink-0 object-contain rounded" />
            <span className="font-medium leading-tight">Powered by Databricks</span>
          </div>
        </div>
        <div className="p-6 border-b border-white/10">
          <Link to="/" className="flex items-center gap-3">
            <img
              src={crestImg}
              alt="Arsenal FC"
              className="h-16 w-16 object-contain drop-shadow-lg flex-shrink-0 ring-2 ring-arsenal-gold/30 rounded-full"
            />
            <div>
              <h1 className="font-display text-xl tracking-widest text-white uppercase leading-none">
                Fan 360
              </h1>
              <p className="text-xs mt-1 text-arsenal-gold">Next Best Action</p>
            </div>
          </Link>
        </div>
        <nav className="flex-1 p-4 space-y-1 overflow-y-auto">
          {navItems.map(({ path, label, icon: Icon }) => {
            const isActive =
              location.pathname === path || (path !== "/" && location.pathname.startsWith(path));
            return (
              <Link
                key={path}
                to={path}
                className={`flex items-center gap-3 px-4 py-2.5 rounded-lg transition-all duration-200 ${
                  isActive
                    ? "text-white font-semibold bg-arsenal-red/20 backdrop-blur-sm border border-arsenal-red/30 shadow-glass-sm"
                    : "text-white/80 border border-transparent hover:bg-white/10 hover:text-white"
                }`}
              >
                <Icon className="w-5 h-5 shrink-0" />
                <span className="text-sm">{label}</span>
              </Link>
            );
          })}
        </nav>
        <div className="p-4 border-t border-white/10 text-[11px] text-white/40 leading-relaxed">
          Governed supporter signals →<br />intelligent next-best-actions.
        </div>
      </aside>

      {/* Main */}
      <main className="relative z-10 flex-1 overflow-auto flex flex-col">
        <div className="sticky top-0 z-40 flex items-center justify-between px-8 py-3 bg-black/30 backdrop-blur-2xl border-b border-white/10">
          <span className="hidden sm:inline font-arsenal-bebas text-lg md:text-xl tracking-[0.14em] text-white/90 uppercase leading-none">
            Turn supporter signals into the next best action
          </span>
          <div className="flex items-center gap-3">
            <span className="text-xs text-white/50">
              {new Date().toLocaleDateString("en-GB", { weekday: "short", day: "numeric", month: "short", year: "numeric" })}
            </span>
            <button
              onClick={() => navigate("/ask")}
              className="inline-flex items-center gap-2 px-5 py-2 bg-arsenal-red/20 backdrop-blur-sm text-white font-semibold rounded-lg border border-arsenal-red/30 hover:bg-arsenal-red/30 hover:border-arsenal-red/50 hover:shadow-glass transition-all duration-200"
            >
              <Sparkles className="w-4 h-4" />
              Ask Genie
            </button>
          </div>
        </div>
        <div className="flex-1 p-8 min-h-0 relative z-10">{children}</div>
      </main>
    </div>
  );
}
