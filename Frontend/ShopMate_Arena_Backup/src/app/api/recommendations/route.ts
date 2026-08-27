import { NextRequest, NextResponse } from "next/server";
import { getPersonalizedRecommendations } from "@/lib/recommender";

export const dynamic = "force-dynamic";

export async function GET(req: NextRequest) {
  const userId = req.nextUrl.searchParams.get("userId") ?? "anon";
  const q = req.nextUrl.searchParams.get("q") ?? undefined;
  const limit = Number(req.nextUrl.searchParams.get("limit") ?? "8");
  const items = await getPersonalizedRecommendations(userId, limit, q);
  return NextResponse.json({ products: items });
}
