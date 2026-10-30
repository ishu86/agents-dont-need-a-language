import type { Ctx, Db, Result } from "./types.ts";
import { err, ok } from "./types.ts";
import { record } from "./audit.ts";

export interface StockLine {
  sku: string;
  qty: number;
}

export function stockOf(db: Db, sku: string): number {
  return db.stock.get(sku) ?? 0;
}

/** Increases stock of `sku` in `ctx.db` and audits it. Returns the new level. */
export function addStock(ctx: Ctx, sku: string, qty: number): Result<number> {
  if (!ctx.db.products.has(sku)) return err("not_found", `unknown sku ${sku}`);
  if (!Number.isInteger(qty) || qty <= 0) return err("invalid", "qty must be a positive integer");
  const level = stockOf(ctx.db, sku) + qty;
  ctx.db.stock.set(sku, level);
  record(ctx.log, ctx.clock, "stock_added", sku, String(qty));
  return ok(level);
}

/** All-or-nothing: decrements stock for every line, or changes nothing and fails. */
export function reserve(db: Db, lines: readonly StockLine[]): Result<void> {
  for (const line of lines) {
    if (stockOf(db, line.sku) < line.qty) {
      return err("out_of_stock", `not enough stock for ${line.sku}`);
    }
  }
  for (const line of lines) {
    db.stock.set(line.sku, stockOf(db, line.sku) - line.qty);
  }
  return ok(undefined);
}

/** Puts units back into stock. */
export function release(db: Db, lines: readonly StockLine[]): void {
  for (const line of lines) {
    db.stock.set(line.sku, stockOf(db, line.sku) + line.qty);
  }
}
