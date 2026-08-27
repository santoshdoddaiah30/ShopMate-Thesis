"use client";

import { useEffect, useRef, useState } from "react";
import type { Product } from "@/db/schema";

export type ChatMsg = {
  role: "user" | "assistant";
  content: string;
  recommendedProductIds?: number[];
};

type Props = {
  userId: string;
  onNewRecommendations: (products: Product[], candidates: Product[]) => void;
  onReset: () => void;
};

export function ChatPanel({ userId, onNewRecommendations, onReset }: Props) {
  const [messages, setMessages] = useState<ChatMsg[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [historyLoaded, setHistoryLoaded] = useState(false);
  const scrollRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    fetch(`/api/chat?userId=${encodeURIComponent(userId)}`)
      .then((r) => r.json())
      .then((d) => {
        const msgs = (d.messages ?? []).map(
          (m: {
            role: string;
            content: string;
            recommendedProductIds?: number[];
          }) => ({
            role: m.role as "user" | "assistant",
            content: m.content,
            recommendedProductIds: m.recommendedProductIds ?? [],
          }),
        );
        if (msgs.length === 0) {
          setMessages([
            {
              role: "assistant",
              content:
                "Hey! I'm ShopMate 🛍️ — your personalized shopping assistant. Tell me what you're looking for (e.g. \"noise-cancelling headphones under $250\", \"a gift for a coffee lover\", \"home gym essentials\") and I'll find the best picks for you.",
            },
          ]);
        } else {
          setMessages(msgs);
        }
        setHistoryLoaded(true);
      });
  }, [userId]);

  useEffect(() => {
    scrollRef.current?.scrollTo({
      top: scrollRef.current.scrollHeight,
      behavior: "smooth",
    });
  }, [messages, loading]);

  async function send(text?: string) {
    const msg = (text ?? input).trim();
    if (!msg || loading) return;
    setInput("");
    setMessages((prev) => [...prev, { role: "user", content: msg }]);
    setLoading(true);
    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ userId, message: msg }),
      });
      const data = await res.json();
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: data.reply ?? "Sorry, something went wrong.",
          recommendedProductIds: (data.recommended ?? []).map(
            (p: Product) => p.id,
          ),
        },
      ]);
      onNewRecommendations(data.recommended ?? [], data.candidates ?? []);
    } catch {
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: "Network error — please try again." },
      ]);
    } finally {
      setLoading(false);
    }
  }

  async function reset() {
    if (!confirm("Clear chat history and preferences?")) return;
    await fetch("/api/reset", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ userId }),
    });
    setMessages([
      {
        role: "assistant",
        content: "Fresh start! What are you shopping for today?",
      },
    ]);
    onReset();
  }

  const suggestions = [
    "Best noise cancelling headphones under $300",
    "A thoughtful gift for a coffee lover",
    "Home gym essentials for a small apartment",
    "Skincare for sensitive dry skin",
  ];

  return (
    <div className="flex h-full flex-col rounded-3xl border border-slate-200 bg-white shadow-sm">
      <div className="flex items-center justify-between border-b border-slate-100 px-5 py-4">
        <div className="flex items-center gap-2">
          <div className="grid h-9 w-9 place-items-center rounded-full bg-gradient-to-br from-indigo-500 to-purple-600 text-lg">
            🛍️
          </div>
          <div>
            <div className="text-sm font-semibold text-slate-900">ShopMate</div>
            <div className="text-xs text-slate-500">
              Personalized · Amazon 2023 catalog
            </div>
          </div>
        </div>
        <button
          onClick={reset}
          className="rounded-lg border border-slate-200 px-3 py-1.5 text-xs text-slate-600 hover:bg-slate-50"
        >
          Reset
        </button>
      </div>

      <div
        ref={scrollRef}
        className="flex-1 space-y-4 overflow-y-auto px-5 py-4"
      >
        {!historyLoaded && (
          <div className="text-center text-sm text-slate-400">Loading…</div>
        )}
        {messages.map((m, i) => (
          <div
            key={i}
            className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}
          >
            <div
              className={`max-w-[85%] whitespace-pre-wrap rounded-2xl px-4 py-3 text-sm leading-relaxed ${
                m.role === "user"
                  ? "bg-indigo-600 text-white"
                  : "bg-slate-100 text-slate-800"
              }`}
            >
              {m.content}
            </div>
          </div>
        ))}
        {loading && (
          <div className="flex justify-start">
            <div className="rounded-2xl bg-slate-100 px-4 py-3 text-sm text-slate-500">
              <span className="inline-flex gap-1">
                <span className="h-2 w-2 animate-bounce rounded-full bg-slate-400" />
                <span className="h-2 w-2 animate-bounce rounded-full bg-slate-400 [animation-delay:0.15s]" />
                <span className="h-2 w-2 animate-bounce rounded-full bg-slate-400 [animation-delay:0.3s]" />
              </span>
            </div>
          </div>
        )}
      </div>

      {messages.length <= 1 && !loading && (
        <div className="border-t border-slate-100 px-5 py-3">
          <div className="mb-2 text-xs font-medium text-slate-500">
            Try asking:
          </div>
          <div className="flex flex-wrap gap-2">
            {suggestions.map((s) => (
              <button
                key={s}
                onClick={() => send(s)}
                className="rounded-full border border-slate-200 bg-white px-3 py-1.5 text-xs text-slate-700 hover:border-indigo-300 hover:bg-indigo-50"
              >
                {s}
              </button>
            ))}
          </div>
        </div>
      )}

      <div className="border-t border-slate-100 p-4">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            send();
          }}
          className="flex items-end gap-2"
        >
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                send();
              }
            }}
            rows={1}
            placeholder="Ask for a recommendation…"
            className="flex-1 resize-none rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm outline-none focus:border-indigo-400 focus:bg-white"
          />
          <button
            type="submit"
            disabled={loading || !input.trim()}
            className="rounded-2xl bg-indigo-600 px-4 py-3 text-sm font-semibold text-white shadow-sm hover:bg-indigo-700 disabled:cursor-not-allowed disabled:bg-slate-300"
          >
            Send
          </button>
        </form>
      </div>
    </div>
  );
}
