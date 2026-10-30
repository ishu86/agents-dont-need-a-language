// Shared runtime state for shopcore.

export const state: any = {
  config: null,
  db: null,
  auditLog: null,
  outbox: null,
  rules: null,
  clock: null,
};

export function newDb(): any {
  return {
    products: new Map(),
    stock: new Map(),
    customers: new Map(),
    coupons: new Map(),
    couponUses: new Map(),
    orders: new Map(),
    seq: 0,
  };
}

// Allocates the next order id.
export function nextOrderId(): string {
  state.db.seq += 1;
  return "ord_" + state.db.seq;
}
