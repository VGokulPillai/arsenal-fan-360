import { useEffect, useRef, useState } from "react";
import { api } from "../lib/api";
import ReactMarkdown from "react-markdown";
import { Sparkles, Send } from "lucide-react";

interface Msg { role: "user" | "genie"; text: string; source?: string; rows?: any[] }

export default function AskArsenal() {
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    api.genieSuggestions().then((s) => setSuggestions(s.questions)).catch(() => {});
  }, []);
  useEffect(() => endRef.current?.scrollIntoView({ behavior: "smooth" }), [msgs]);

  const ask = async (question: string) => {
    if (!question.trim() || busy) return;
    setMsgs((m) => [...m, { role: "user", text: question }]);
    setInput("");
    setBusy(true);
    try {
      const res = await api.genieAsk(question);
      setMsgs((m) => [...m, { role: "genie", text: res.answer, source: res.source, rows: res.rows }]);
    } catch (e) {
      setMsgs((m) => [...m, { role: "genie", text: "Sorry, I couldn't reach the Genie space. " + String(e) }]);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="max-w-4xl mx-auto space-y-5">
      <div className="flex items-center gap-3">
        <div className="p-2 rounded-lg bg-arsenal-red/20 text-arsenal-gold"><Sparkles className="w-6 h-6" /></div>
        <div>
          <h1 className="font-display text-3xl tracking-wider text-white uppercase">Ask Arsenal</h1>
          <p className="text-white/60 text-sm">Natural-language supporter intelligence · powered by Databricks Genie</p>
        </div>
      </div>

      {msgs.length === 0 && (
        <div className="glass-card p-6">
          <p className="text-white/70 mb-4">Try one of these:</p>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {suggestions.map((s) => (
              <button key={s} onClick={() => ask(s)}
                className="text-left glass-card-light p-3 text-sm text-white/85 hover:border-arsenal-red/40 transition">
                {s}
              </button>
            ))}
          </div>
        </div>
      )}

      <div className="space-y-4">
        {msgs.map((m, i) => (
          <div key={i} className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
            <div className={`max-w-[85%] rounded-2xl px-4 py-3 ${
              m.role === "user"
                ? "bg-arsenal-red/25 border border-arsenal-red/40 text-white"
                : "glass-card text-white/90"}`}>
              <div className="prose prose-invert prose-sm max-w-none">
                <ReactMarkdown>{m.text}</ReactMarkdown>
              </div>
              {m.rows && m.rows.length > 0 && (
                <div className="mt-3 overflow-auto">
                  <table className="text-xs w-full">
                    <thead className="text-white/50 text-left">
                      <tr>{Object.keys(m.rows[0]).map((k) => <th key={k} className="pr-3 py-1">{k}</th>)}</tr>
                    </thead>
                    <tbody>
                      {m.rows.slice(0, 10).map((row, ri) => (
                        <tr key={ri} className="border-t border-white/10">
                          {Object.values(row).map((v, ci) => <td key={ci} className="pr-3 py-1 text-white/80">{String(v)}</td>)}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
              {m.source && <p className="text-[10px] text-arsenal-gold/80 mt-2">Source: {m.source}</p>}
            </div>
          </div>
        ))}
        {busy && <div className="text-white/50 text-sm animate-pulse-live">Genie is analysing supporter data…</div>}
        <div ref={endRef} />
      </div>

      <div className="glass-card p-3 flex gap-3 items-center sticky bottom-0">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && ask(input)}
          placeholder="Ask about supporters, intent, opportunities…"
          className="flex-1 bg-transparent outline-none text-white placeholder-white/40 px-2"
        />
        <button onClick={() => ask(input)} disabled={busy}
          className="px-4 py-2 rounded-lg bg-arsenal-red text-white flex items-center gap-2 hover:bg-arsenal-red-dark disabled:opacity-60">
          <Send className="w-4 h-4" /> Ask
        </button>
      </div>
    </div>
  );
}
