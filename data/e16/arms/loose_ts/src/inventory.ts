import { state } from "./state.ts";
import { record } from "./audit.ts";

export function stockOf(sku: string): number {
  return state.db.stock.get(sku) || 0;
}

// Increases stock of `sku`. Returns the new level.
export function addStock(sku: string, qty: any): number {
  if (!state.db.products.has(sku)) throw `not_found: unknown sku ${sku}`;
  qty = +qty;
  if (!Number.isInteger(qty) || qty <= 0) throw "invalid: qty must be a positive integer";
  const level = stockOf(sku) + qty;
  state.db.stock.set(sku, level);
  record("stock_added", sku, String(qty));
  return level;
}

// Takes the items out of stock. Returns -1 when all of them were available,
// otherwise the index of the first short item (nothing is taken in that case).
export function reserve(items: any[]): number {
  const short = items.findIndex((i: any) => stockOf(i.sku) < i.qty);
  if (short !== -1) return short;
  for (const i of items) state.db.stock.set(i.sku, stockOf(i.sku) - i.qty);
  return -1;
}

export function release(items: any[]): void {
  for (const i of items) state.db.stock.set(i.sku, stockOf(i.sku) + i.qty);
}

// Skus whose stock is at or below `threshold`.
export function lowStock(threshold: number): string[] {
  const out: string[] = [];
  for (const sku of state.db.products.keys()) {
    if (stockOf(sku) <= threshold) out.push(sku);
  }
  return out.sort();
}

// Total units on hand across all products.
export function totalStock(): number {
  let n = 0;
  for (const level of state.db.stock.values()) n += level;
  return n;
}
