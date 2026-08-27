import { NextResponse } from "next/server";
import { db } from "@/db";
import { products } from "@/db/schema";
import { SEED_PRODUCTS } from "@/lib/seed-data";
import { sql } from "drizzle-orm";

export const dynamic = "force-dynamic";

async function seed() {
  const [{ count }] = await db
    .select({ count: sql<number>`count(*)::int` })
    .from(products);
  if (count > 0) {
    return { ok: true, message: `Already seeded (${count} products).`, count };
  }
  await db.insert(products).values(SEED_PRODUCTS);
  return { ok: true, message: "Seeded catalog.", count: SEED_PRODUCTS.length };
}

export async function GET() {
  const result = await seed();
  return NextResponse.json(result);
}

export async function POST() {
  const result = await seed();
  return NextResponse.json(result);
}
