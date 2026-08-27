import type { Product } from "@/db/schema";
import type { UserProfile } from "./recommender";

export type ChatTurn = { role: "user" | "assistant"; content: string };

function buildSystemPrompt(profile: UserProfile, candidates: Product[]): string {
  const topCats = Object.entries(profile.categoryScores)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 5)
    .map(([k]) => k);
  const topTags = Object.entries(profile.tagScores)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 8)
    .map(([k]) => k);

  const catalog = candidates
    .map(
      (p, i) =>
        `${i + 1}. [id:${p.id}] ${p.title} — ${p.category}/${p.subcategory ?? ""} — $${p.price} — ★${p.rating} (${p.reviewCount} reviews) — tags: ${(p.tags ?? []).join(", ")}`,
    )
    .join("\n");

  return `You are ShopMate, a friendly, concise personalized shopping assistant powered by an Amazon 2023 product catalog. Your job:
1) Understand what the shopper wants (occasion, budget, preferences).
2) Recommend from the candidate products below, tailored to their profile.
3) Explain WHY each recommendation fits.
4) Ask a short follow-up question if helpful.

USER PROFILE
- Total past interactions: ${profile.totalInteractions}
- Preferred categories: ${topCats.join(", ") || "unknown yet"}
- Preferred tags: ${topTags.join(", ") || "unknown yet"}
- Typical price point: ${profile.avgPrice ? "$" + profile.avgPrice.toFixed(0) : "unknown"}

CANDIDATE PRODUCTS (choose 2-4 that best fit, referring to them by title):
${catalog}

Rules:
- Keep the reply under 180 words, warm and helpful.
- Recommend AT MOST 4 products, only from the candidate list.
- End with a short follow-up question.
- Never invent products not in the list.`;
}

type ChatResult = { text: string; productIds: number[] };

export async function generateChatReply(
  messages: ChatTurn[],
  profile: UserProfile,
  candidates: Product[],
): Promise<ChatResult> {
  const systemPrompt = buildSystemPrompt(profile, candidates);
  const apiKey = process.env.OPENAI_API_KEY;

  if (apiKey) {
    try {
      const res = await fetch("https://api.openai.com/v1/chat/completions", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${apiKey}`,
        },
        body: JSON.stringify({
          model: process.env.OPENAI_MODEL || "gpt-4o-mini",
          temperature: 0.7,
          messages: [
            { role: "system", content: systemPrompt },
            ...messages.map((m) => ({ role: m.role, content: m.content })),
          ],
        }),
      });
      if (res.ok) {
        const data = await res.json();
        const text: string =
          data?.choices?.[0]?.message?.content?.trim() ??
          "I'm here to help you find the perfect product — what are you shopping for today?";
        const productIds = extractReferencedProductIds(text, candidates);
        return { text, productIds };
      }
    } catch (e) {
      console.error("OpenAI call failed, falling back:", e);
    }
  }

  return fallbackReply(messages, profile, candidates);
}

function extractReferencedProductIds(text: string, candidates: Product[]): number[] {
  const lower = text.toLowerCase();
  const ids: number[] = [];
  for (const p of candidates) {
    // match by title fragment (first 4 words) or brand + first noun
    const key = p.title.toLowerCase();
    const shortKey = key.split(" ").slice(0, 4).join(" ");
    if (lower.includes(shortKey) || lower.includes(`id:${p.id}`)) {
      ids.push(p.id);
    }
  }
  return ids.slice(0, 4);
}

function fallbackReply(
  messages: ChatTurn[],
  profile: UserProfile,
  candidates: Product[],
): ChatResult {
  const lastUser = [...messages].reverse().find((m) => m.role === "user")?.content ?? "";
  const q = lastUser.toLowerCase();

  // simple keyword scoring against candidates
  const words = q
    .replace(/[^a-z0-9\s]/g, " ")
    .split(/\s+/)
    .filter((w) => w.length > 2);
  const scored = candidates.map((p) => {
    const hay = (
      p.title +
      " " +
      p.category +
      " " +
      (p.subcategory ?? "") +
      " " +
      (p.tags ?? []).join(" ") +
      " " +
      p.description
    ).toLowerCase();
    let s = 0;
    for (const w of words) if (hay.includes(w)) s += 2;
    s += p.rating * 0.5;
    s += (profile.categoryScores[p.category] ?? 0) * 0.5;
    for (const t of p.tags ?? []) s += (profile.tagScores[t] ?? 0) * 0.3;
    return { p, s };
  });
  scored.sort((a, b) => b.s - a.s);
  const picks = scored.slice(0, 3).map((x) => x.p);

  const intro =
    profile.totalInteractions === 0
      ? "Welcome! Based on our top-rated catalog, here are a few great picks:"
      : `Based on your interest in ${Object.keys(profile.categoryScores).slice(0, 2).join(" & ") || "quality products"}, here are personalized picks:`;

  const bullets = picks
    .map(
      (p) =>
        `• **${p.title}** — $${p.price} · ★${p.rating}. ${p.description.split(".")[0]}.`,
    )
    .join("\n");

  const followUp =
    words.length === 0
      ? "\n\nWhat are you shopping for today — a gift, an upgrade, or something for yourself?"
      : "\n\nWould you like me to narrow this down by budget or brand?";

  return {
    text: `${intro}\n\n${bullets}${followUp}`,
    productIds: picks.map((p) => p.id),
  };
}
