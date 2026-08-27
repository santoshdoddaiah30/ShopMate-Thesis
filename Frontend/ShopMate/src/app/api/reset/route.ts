import { NextRequest, NextResponse } from "next/server";
import { db } from "@/db";
import { chatMessages, interactions } from "@/db/schema";
import { eq } from "drizzle-orm";

export const dynamic = "force-dynamic";

export async function POST(req: NextRequest) {
  const body = await req.json().catch(() => ({}));
  const userId: string = body.userId ?? "anon";
  await db.delete(chatMessages).where(eq(chatMessages.userId, userId));
  await db.delete(interactions).where(eq(interactions.userId, userId));
  return NextResponse.json({ ok: true });
}
