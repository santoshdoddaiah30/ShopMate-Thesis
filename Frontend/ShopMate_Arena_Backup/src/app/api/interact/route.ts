import { NextRequest, NextResponse } from "next/server";
import { db } from "@/db";
import { interactions } from "@/db/schema";

export const dynamic = "force-dynamic";

const VALID = new Set(["view", "like", "cart", "purchase"]);

export async function POST(req: NextRequest) {
  const body = await req.json();
  const userId: string = body.userId ?? "anon";
  const productId: number = Number(body.productId);
  const kind: string = String(body.kind ?? "view");
  if (!productId || !VALID.has(kind)) {
    return NextResponse.json({ error: "invalid input" }, { status: 400 });
  }
  await db.insert(interactions).values({ userId, productId, kind });
  return NextResponse.json({ ok: true });
}
