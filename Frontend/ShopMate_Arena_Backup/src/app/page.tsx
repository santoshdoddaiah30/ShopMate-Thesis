"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import type { Product } from "@/db/schema";
import { getOrCreateClientUserId } from "@/lib/user";
import { ChatPanel } from "@/components/ChatPanel";
import { ProductCard } from "@/components/ProductCard";

export default function HomePage() {
  const [userId, setUserId] = useState<string>("");
  const [recommended, setRecommended] = useState<Product[]>([]);
  const [candidates, setCandidates] = useState<Product[]>([]);
  const [seeded, setSeeded] = useState(false);

  useEffect(() => {
    setUserId(getOrCreateClientUserId());
  }, []);

  const refreshFeed = useCallback(async (uid: string) => {
    const r = await fetch(
      `/api/recommendations?userId=${encodeURIComponent(uid)}&limit=12`,
    );
    const d = await r.json();
    setCandidates(d.products ?? []);
  }, []);

  useEffect(() => {
    if (!userId) return;
    (async () => {
      // ensure seeded
      const s = await fetch("/api/seed").then((r) => r.json());
      setSeeded(s.ok);
      await refreshFeed(userId);
    })();
  }, [userId, refreshFeed]);

  const highlightedIds = useMemo(
    () => new Set(recommended.map((p) => p.id)),
    [recommended],
  );

  async function handleInteract(
    p: Product,
    kind: "view" | "like" | "cart" | "purchase",
  ) {
    await fetch("/api/interact", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ userId, productId: p.id, kind }),
    });
    // refresh personalized feed to reflect updated profile
    refreshFeed(userId);
  }

  const displayProducts = useMemo(() => {
    // Show highlighted recs first, then the rest of the candidates (dedup)
    const seen = new Set<number>();
    const merged: Product[] = [];
    for (const p of recommended) {
      if (!seen.has(p.id)) {
        merged.push(p);
        seen.add(p.id);
      }
    }
    for (const p of candidates) {
      if (!seen.has(p.id)) {
        merged.push(p);
        seen.add(p.id);
      }
    }
    return merged;
  }, [recommended, candidates]);

  if (!userId) {
    return (
      <main className="grid min-h-screen place-items-center">
        <div className="text-slate-500">Loading…</div>
      </main>
    );
  }

  return (
    <main className="mx-auto flex min-h-screen max-w-[1400px] flex-col gap-6 px-4 py-6 lg:px-8">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900 sm:text-3xl">
            ShopMate <span className="text-indigo-600">·</span> Personalized Shopping AI
          </h1>
          <p className="mt-1 text-sm text-slate-600">
            A ChatGPT-style assistant that learns from your clicks & purchases
            to recommend from an Amazon 2023 catalog.
          </p>
        </div>
        <div className="flex items-center gap-3 text-xs text-slate-500">
          <span className="rounded-full bg-emerald-50 px-3 py-1 font-medium text-emerald-700">
            {seeded ? "Catalog ready" : "Loading catalog…"}
          </span>
          <span className="rounded-full bg-slate-100 px-3 py-1 font-mono">
            {userId}
          </span>
        </div>
      </header>

      <div className="grid flex-1 grid-cols-1 gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.4fr)]">
        <section className="h-[calc(100vh-180px)] min-h-[560px] lg:sticky lg:top-6">
          <ChatPanel
            userId={userId}
            onNewRecommendations={(recs, cands) => {
              setRecommended(recs);
              if (cands.length > 0) setCandidates(cands);
            }}
            onReset={() => {
              setRecommended([]);
              refreshFeed(userId);
            }}
          />
        </section>

        <section className="min-w-0">
          <div className="mb-3 flex items-center justify-between">
            <h2 className="text-lg font-semibold text-slate-900">
              {recommended.length > 0
                ? "Recommended for you"
                : "Personalized picks"}
            </h2>
            <span className="text-xs text-slate-500">
              {displayProducts.length} products · click to personalize
            </span>
          </div>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
            {displayProducts.map((p) => (
              <ProductCard
                key={p.id}
                product={p}
                highlighted={highlightedIds.has(p.id)}
                onInteract={(k) => handleInteract(p, k)}
              />
            ))}
          </div>
          {displayProducts.length === 0 && (
            <div className="rounded-2xl border border-dashed border-slate-300 p-12 text-center text-sm text-slate-500">
              Loading products…
            </div>
          )}
        </section>
      </div>

      <footer className="pb-6 pt-2 text-center text-xs text-slate-400">
        Built with Next.js, Drizzle & PostgreSQL. Personalization improves as
        you interact. LLM: OpenAI (with rule-based fallback).
      </footer>
    </main>
  );
}
