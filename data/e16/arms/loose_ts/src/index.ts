// Public API of shopcore.
import { state, newDb } from "./state.ts";
import { makeConfig } from "./config.ts";
import { addProduct, getProduct, listProducts } from "./catalog.ts";
import { addStock, stockOf } from "./inventory.ts";
import { addCustomer, getCustomer, tierOf } from "./customers.ts";
import { addCoupon, ruleRegistry } from "./pricing.ts";
import "./rules/bulk.ts";
import "./rules/vip.ts";
import "./rules/coupon.ts";
import { addItem, applyCoupon, checkout, createOrder, getOrder } from "./orders.ts";
import { refund } from "./refunds.ts";
import { listOutbox } from "./notifications.ts";
import { entries } from "./audit.ts";

// Internal code throws "code: message" strings; this is where they become results.
function toResult(fn: (...a: any[]) => any, args: any[]): any {
  try {
    return { ok: true, value: fn(...args) };
  } catch (e) {
    if (typeof e !== "string") throw e;
    const i = e.indexOf(": ");
    return { ok: false, error: { code: e.slice(0, i), message: e.slice(i + 2) } };
  }
}

export function createShop(options?: any) {
  options = options || {};
  const mine = {
    config: makeConfig(options.config),
    db: newDb(),
    auditLog: [],
    outbox: [],
    rules: options.rules || ruleRegistry.slice(),
    clock: { now: options.now || (() => Date.now()) },
  };
  const result = (fn: (...a: any[]) => any) => (...args: any[]) => { Object.assign(state, mine); return toResult(fn, args); };
  const plain = (fn: (...a: any[]) => any) => (...args: any[]) => { Object.assign(state, mine); return fn(...args); };

  return {
    addProduct: result(addProduct),
    addStock: result(addStock),
    addCustomer: result(addCustomer),
    addCoupon: result(addCoupon),
    createOrder: result(createOrder),
    addItem: result(addItem),
    applyCoupon: result(applyCoupon),
    checkout: result(checkout),
    refund: result(refund),
    getOrder: plain((id: string) => getOrder(id) || undefined),
    getProduct: plain((sku: string) => getProduct(sku) || undefined),
    listProducts: plain(listProducts),
    getCustomer: plain((id: string) => getCustomer(id) || undefined),
    // Name of the customer's current VIP tier, e.g. "none", "silver", "gold".
    tier: plain((id: string) => {
      const c = getCustomer(id);
      return c ? tierOf(c).name : undefined;
    }),
    stock: plain(stockOf),
    outbox: plain(listOutbox),
    audit: plain(entries),
  };
}
