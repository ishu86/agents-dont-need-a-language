import type { AuditLog, Db } from "./types.ts";

export function createDb(): Db {
  return {
    products: new Map(),
    stock: new Map(),
    customers: new Map(),
    coupons: new Map(),
    couponUses: new Map(),
    orders: new Map(),
    outbox: [],
    seq: 0,
  };
}

export function createLog(): AuditLog {
  return { entries: [] };
}

/** Allocates the next order id. Mutates `db.seq`. */
export function nextOrderId(db: Db): string {
  db.seq += 1;
  return `ord_${db.seq}`;
}
