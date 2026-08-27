import { db } from "@/db";
import { products, interactions, type Product } from "@/db/schema";
import { desc, eq, sql, inArray } from "drizzle-orm";

const WEIGHTS: Record<string, number> = {
  view: 1,
  like: 3,
  cart: 4,
  purchase: 5,
};

export type UserProfile = {
  tagScores: Record<string, number>;
  categoryScores: Record<string, number>;
  brandScores: Record<string, number>;
  avgPrice: number | null;
  seenProductIds: Set<number>;
  totalInteractions: number;
};

export async function buildUserProfile(userId: string): Promise<UserProfile> {
  const rows = await db
    .select({
      productId: interactions.productId,
      kind: interactions.kind,
      category: products.category,
      tags: products.tags,
      brand: products.brand,
      price: products.price,
    })
    .from(interactions)
    .innerJoin(products, eq(interactions.productId, products.id))
    .where(eq(interactions.userId, userId))
    .orderBy(desc(interactions.createdAt))
    .limit(200);

  const tagScores: Record<string, number> = {};
  const categoryScores: Record<string, number> = {};
  const brandScores: Record<string, number> = {};
  const seen = new Set<number>();
  let priceSum = 0;
  let priceCount = 0;

  for (const r of rows) {
    const w = WEIGHTS[r.kind] ?? 1;
    seen.add(r.productId);
    categoryScores[r.category] = (categoryScores[r.category] ?? 0) + w;
    if (r.brand) brandScores[r.brand] = (brandScores[r.brand] ?? 0) + w;
    for (const t of r.tags ?? []) {
      tagScores[t] = (tagScores[t] ?? 0) + w;
    }
    priceSum += r.price;
    priceCount += 1;
  }

  return {
    tagScores,
    categoryScores,
    brandScores,
    avgPrice: priceCount ? priceSum / priceCount : null,
    seenProductIds: seen,
    totalInteractions: rows.length,
  };
}

export function scoreProduct(p: Product, profile: UserProfile): number {
  let score = 0;
  score += (profile.categoryScores[p.category] ?? 0) * 2;
  if (p.brand) score += profile.brandScores[p.brand] ?? 0;
  for (const t of p.tags ?? []) {
    score += profile.tagScores[t] ?? 0;
  }
  // Quality boost
  score += p.rating * 0.6;
  score += Math.log10(Math.max(1, p.reviewCount)) * 0.3;
  // Price alignment
  if (profile.avgPrice != null) {
    const diff = Math.abs(p.price - profile.avgPrice) / (profile.avgPrice + 1);
    score -= diff * 0.5;
  }
  // Avoid re-recommending things they've heavily engaged with
  if (profile.seenProductIds.has(p.id)) score -= 3;
  return score;
}

export async function getPersonalizedRecommendations(
  userId: string,
  limit = 8,
  filterQuery?: string,
): Promise<Product[]> {
  const profile = await buildUserProfile(userId);
  let candidates: Product[];

  if (filterQuery && filterQuery.trim()) {
    const q = `%${filterQuery.toLowerCase()}%`;
    candidates = await db
      .select()
      .from(products)
      .where(
        sql`(lower(${products.title}) like ${q}
           or lower(${products.description}) like ${q}
           or lower(${products.category}) like ${q}
           or lower(${products.subcategory}) like ${q}
           or exists (
             select 1 from jsonb_array_elements_text(${products.tags}) t
             where lower(t) like ${q}
           ))`,
      )
      .limit(80);
    if (candidates.length === 0) {
      candidates = await db.select().from(products).limit(200);
    }
  } else {
    candidates = await db.select().from(products).limit(200);
  }

  const scored = candidates
    .map((p) => ({ p, s: scoreProduct(p, profile) }))
    .sort((a, b) => b.s - a.s);

  // If the user has no history, fall back to top-rated popular items
  if (profile.totalInteractions === 0 && !filterQuery) {
    return candidates
      .slice()
      .sort(
        (a, b) =>
          b.rating * Math.log10(Math.max(10, b.reviewCount)) -
          a.rating * Math.log10(Math.max(10, a.reviewCount)),
      )
      .slice(0, limit);
  }

  return scored.slice(0, limit).map((x) => x.p);
}

export async function getProductsByIds(ids: number[]): Promise<Product[]> {
  if (ids.length === 0) return [];
  const rows = await db.select().from(products).where(inArray(products.id, ids));
  // preserve requested order
  const map = new Map(rows.map((r) => [r.id, r]));
  return ids.map((i) => map.get(i)).filter((x): x is Product => !!x);
}
