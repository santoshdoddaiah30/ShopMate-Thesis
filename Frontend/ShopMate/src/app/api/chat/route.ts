import { NextRequest, NextResponse } from "next/server";
import { db } from "@/db";
import { chatMessages } from "@/db/schema";
import { asc, eq } from "drizzle-orm";
import {
  buildUserProfile,
  getPersonalizedRecommendations,
  getProductsByIds,
} from "@/lib/recommender";
import { generateChatReply, type ChatTurn } from "@/lib/chat";

export const dynamic = "force-dynamic";

export async function GET(req: NextRequest) {
  const userId = req.nextUrl.searchParams.get("userId") ?? "anon";
  const rows = await db
    .select()
    .from(chatMessages)
    .where(eq(chatMessages.userId, userId))
    .orderBy(asc(chatMessages.createdAt))
    .limit(100);
  return NextResponse.json({ messages: rows });
}

export async function POST(req: NextRequest) {
  const body = await req.json();
  const userId: string = body.userId ?? "anon";
  const message: string = (body.message ?? "").toString().trim();
  if (!message) {
    return NextResponse.json({ error: "empty message" }, { status: 400 });
  }

  // 1) Save user turn
  await db.insert(chatMessages).values({
    userId,
    role: "user",
    content: message,
    recommendedProductIds: [],
  });

  // 2) Load recent history
  const history = await db
    .select()
    .from(chatMessages)
    .where(eq(chatMessages.userId, userId))
    .orderBy(asc(chatMessages.createdAt))
    .limit(20);
  const turns: ChatTurn[] = history.map((m) => ({
    role: m.role as "user" | "assistant",
    content: m.content,
  }));

  // 3) Build profile + candidate products (filtered by current query)
  const profile = await buildUserProfile(userId);
  const candidates = await getPersonalizedRecommendations(userId, 12, message);

  // 4) LLM reply (or fallback)
  const { text, productIds } = await generateChatReply(turns, profile, candidates);

  // 5) Persist assistant turn
  await db.insert(chatMessages).values({
    userId,
    role: "assistant",
    content: text,
    recommendedProductIds: productIds,
  });

  const recommended = await getProductsByIds(productIds);

  return NextResponse.json({
    reply: text,
    recommended,
    candidates, // panel of related products to explore
  });
}
