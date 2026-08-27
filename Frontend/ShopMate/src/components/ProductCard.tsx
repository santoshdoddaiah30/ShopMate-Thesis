"use client";

import type { Product } from "@/db/schema";

type Props = {
  product: Product;
  onInteract: (kind: "view" | "like" | "cart" | "purchase") => void;
  highlighted?: boolean;
};

export function ProductCard({ product, onInteract, highlighted }: Props) {
  return (
    <div
      className={`group flex flex-col rounded-2xl border bg-white p-4 shadow-sm transition hover:shadow-lg ${
        highlighted ? "border-indigo-400 ring-2 ring-indigo-200" : "border-slate-200"
      }`}
    >
      <div className="mb-3 flex h-28 items-center justify-center rounded-xl bg-gradient-to-br from-slate-100 to-slate-200 text-6xl">
        <span>{product.imageEmoji}</span>
      </div>
      <div className="mb-1 flex items-center gap-2 text-xs text-slate-500">
        <span className="font-medium">{product.brand ?? "Amazon"}</span>
        <span>·</span>
        <span>{product.category}</span>
      </div>
      <h3 className="line-clamp-2 text-sm font-semibold leading-snug text-slate-900">
        {product.title}
      </h3>
      <div className="mt-2 flex items-center gap-2 text-xs">
        <span className="rounded-full bg-amber-50 px-2 py-0.5 font-semibold text-amber-700">
          ★ {product.rating.toFixed(1)}
        </span>
        <span className="text-slate-500">
          ({product.reviewCount.toLocaleString()})
        </span>
      </div>
      <p className="mt-2 line-clamp-2 text-xs text-slate-600">{product.description}</p>
      <div className="mt-3 flex flex-wrap gap-1">
        {(product.tags ?? []).slice(0, 3).map((t) => (
          <span
            key={t}
            className="rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-medium text-slate-600"
          >
            {t}
          </span>
        ))}
      </div>
      <div className="mt-auto flex items-end justify-between pt-3">
        <div className="text-xl font-bold text-slate-900">
          ${product.price.toFixed(2)}
        </div>
        <div className="flex gap-1">
          <button
            onClick={() => onInteract("like")}
            className="rounded-lg border border-slate-200 px-2 py-1 text-xs text-slate-600 hover:bg-slate-50"
            title="Like"
          >
            ♡
          </button>
          <button
            onClick={() => onInteract("cart")}
            className="rounded-lg border border-slate-200 px-2 py-1 text-xs text-slate-600 hover:bg-slate-50"
            title="Add to cart"
          >
            🛒
          </button>
          <button
            onClick={() => onInteract("purchase")}
            className="rounded-lg bg-indigo-600 px-2 py-1 text-xs font-semibold text-white hover:bg-indigo-700"
            title="Buy"
          >
            Buy
          </button>
        </div>
      </div>
    </div>
  );
}
