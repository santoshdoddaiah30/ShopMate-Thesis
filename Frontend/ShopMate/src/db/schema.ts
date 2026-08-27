import {
  pgTable,
  serial,
  text,
  varchar,
  integer,
  real,
  timestamp,
  jsonb,
  index,
} from "drizzle-orm/pg-core";

export const products = pgTable(
  "products",
  {
    id: serial("id").primaryKey(),
    asin: varchar("asin", { length: 32 }).notNull().unique(),
    title: text("title").notNull(),
    brand: varchar("brand", { length: 128 }),
    category: varchar("category", { length: 128 }).notNull(),
    subcategory: varchar("subcategory", { length: 128 }),
    price: real("price").notNull(),
    rating: real("rating").notNull(),
    reviewCount: integer("review_count").notNull().default(0),
    description: text("description").notNull(),
    features: jsonb("features").$type<string[]>().notNull().default([]),
    tags: jsonb("tags").$type<string[]>().notNull().default([]),
    imageEmoji: varchar("image_emoji", { length: 8 }).notNull().default("📦"),
    createdAt: timestamp("created_at").notNull().defaultNow(),
  },
  (t) => [index("products_category_idx").on(t.category)],
);

export const interactions = pgTable(
  "interactions",
  {
    id: serial("id").primaryKey(),
    userId: varchar("user_id", { length: 64 }).notNull(),
    productId: integer("product_id").notNull(),
    // 'view' | 'like' | 'cart' | 'purchase'
    kind: varchar("kind", { length: 16 }).notNull(),
    createdAt: timestamp("created_at").notNull().defaultNow(),
  },
  (t) => [index("interactions_user_idx").on(t.userId)],
);

export const chatMessages = pgTable(
  "chat_messages",
  {
    id: serial("id").primaryKey(),
    userId: varchar("user_id", { length: 64 }).notNull(),
    role: varchar("role", { length: 16 }).notNull(), // 'user' | 'assistant'
    content: text("content").notNull(),
    recommendedProductIds: jsonb("recommended_product_ids")
      .$type<number[]>()
      .notNull()
      .default([]),
    createdAt: timestamp("created_at").notNull().defaultNow(),
  },
  (t) => [index("chat_messages_user_idx").on(t.userId)],
);

export type Product = typeof products.$inferSelect;
export type NewProduct = typeof products.$inferInsert;
export type Interaction = typeof interactions.$inferSelect;
export type ChatMessage = typeof chatMessages.$inferSelect;
