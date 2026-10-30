import { state } from "./state.js";
import { record } from "./audit.js";

export function stockOf(sku) {
  return state.db.stock.get(sku) || 0;
}

// Increases stock of `sku`. Returns the new level.
export function addStock(sku, qty) {
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
export function reserve(items) {
  const short = items.findIndex((i) => stockOf(i.sku) < i.qty);
  if (short !== -1) return short;
  for (const i of items) state.db.stock.set(i.sku, stockOf(i.sku) - i.qty);
  return -1;
}

export function release(items) {
  for (const i of items) state.db.stock.set(i.sku, stockOf(i.sku) + i.qty);
}

// Skus whose stock is at or below `threshold`.
export function lowStock(threshold) {
  const out = [];
  for (const sku of state.db.products.keys()) {
    if (stockOf(sku) <= threshold) out.push(sku);
  }
  return out.sort();
}

// Total units on hand across all products.
export function totalStock() {
  let n = 0;
  for (const level of state.db.stock.values()) n += level;
  return n;
}
