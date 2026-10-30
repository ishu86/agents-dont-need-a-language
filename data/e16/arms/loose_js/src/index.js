// Public API of shopcore.
import { state, newDb } from "./state.js";
import { makeConfig } from "./config.js";
import { addProduct, getProduct, listProducts } from "./catalog.js";
import { addStock, stockOf } from "./inventory.js";
import { addCustomer, getCustomer, tierOf } from "./customers.js";
import { addCoupon, ruleRegistry } from "./pricing.js";
import "./rules/bulk.js";
import "./rules/vip.js";
import "./rules/coupon.js";
import { addItem, applyCoupon, checkout, createOrder, getOrder } from "./orders.js";
import { refund } from "./refunds.js";
import { listOutbox } from "./notifications.js";
import { entries } from "./audit.js";

// Internal code throws "code: message" strings; this is where they become results.
function toResult(fn, args) {
  try {
    return { ok: true, value: fn(...args) };
  } catch (e) {
    if (typeof e !== "string") throw e;
    const i = e.indexOf(": ");
    return { ok: false, error: { code: e.slice(0, i), message: e.slice(i + 2) } };
  }
}

export function createShop(options) {
  options = options || {};
  const mine = {
    config: makeConfig(options.config),
    db: newDb(),
    auditLog: [],
    outbox: [],
    rules: options.rules || ruleRegistry.slice(),
    clock: { now: options.now || (() => Date.now()) },
  };
  const result = (fn) => (...args) => { Object.assign(state, mine); return toResult(fn, args); };
  const plain = (fn) => (...args) => { Object.assign(state, mine); return fn(...args); };

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
    getOrder: plain((id) => getOrder(id) || undefined),
    getProduct: plain((sku) => getProduct(sku) || undefined),
    listProducts: plain(listProducts),
    getCustomer: plain((id) => getCustomer(id) || undefined),
    // Name of the customer's current VIP tier, e.g. "none", "silver", "gold".
    tier: plain((id) => {
      const c = getCustomer(id);
      return c ? tierOf(c).name : undefined;
    }),
    stock: plain(stockOf),
    outbox: plain(listOutbox),
    audit: plain(entries),
  };
}
