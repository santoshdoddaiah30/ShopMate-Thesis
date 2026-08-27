import { NextResponse } from "next/server";
import { db } from "@/db";
import { products } from "@/db/schema";
import { asc } from "drizzle-orm";

export const dynamic = "force-dynamic";

export async function GET() {
  const rows = await db.select().from(products).orderBy(asc(products.category));
  return NextResponse.json({ products: rows });
}
