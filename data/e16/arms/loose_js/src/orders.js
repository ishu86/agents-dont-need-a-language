import { state, nextOrderId } from "./state.js";
import { getCustomer, adjustSpend } from "./customers.js";
import { getProduct } from "./catalog.js";
import { reserve } from "./inventory.js";
import { checkCoupon, computeTotal, getCoupon, recordCouponUse } from "./pricing.js";
import { record } from "./audit.js";
import { formatCents } from "./money.js";
import { queueEmail } from "./notifications.js";

export class Order {
  constructor(id, customerId, shipRegion) {
    this.id = id;
    this.customerId = customerId;
    this.shipRegion = shipRegion;
    this.items = [];
    this.couponCode = null;
    this.status = "open";
    this.pricing = null;
    this.lineNetCents = {};
    this.refundedByLine = {};
    this.refundedCents = 0;
    this.createdAt = state.clock.now();
    this.paidAt = null;
  }
}

export function getOrder(id) {
  return state.db.orders.get(id) || null;
}

function loadOrder(id) {
  const order = getOrder(id);
  if (!order) throw `not_found: unknown order ${id}`;
  return order;
}

export function createOrder(input) {
  const customer = getCustomer(input.customerId);
  if (!customer) throw `not_found: unknown customer ${input.customerId}`;
  const order = new Order(nextOrderId(), customer.id, input.shipRegion || customer.region);
  computeTotal(order);
  state.db.orders.set(order.id, order);
  record("order_created", order.id, customer.id);
  return order;
}

export function addItem(orderId, sku, qty) {
  const order = loadOrder(orderId);
  if (order.status !== "open") throw `bad_state: order ${orderId} is ${order.status}`;
  const product = getProduct(sku);
  if (!product) throw `not_found: unknown sku ${sku}`;
  if (!Number.isInteger(qty) || qty <= 0) throw "invalid: qty must be a positive integer";

  const existing = order.items.find((i) => i.sku === sku);
  if (existing) existing.qty += qty;
  else order.items.push({ sku, qty, unitPriceCents: product.priceCents });
  computeTotal(order);
  return order;
}

export function applyCoupon(orderId, code) {
  const order = loadOrder(orderId);
  if (order.status !== "open") throw `bad_state: order ${orderId} is ${order.status}`;
  const coupon = getCoupon(code);
  if (!coupon) throw `coupon_invalid: unknown coupon ${code}`;
  const bad = checkCoupon(coupon, order.pricing.subtotalCents);
  if (bad) throw bad;
  order.couponCode = code;
  computeTotal(order);
  record("coupon_applied", orderId, code);
  return order;
}

// Pays an open order: reprices, validates the coupon, reserves stock, redeems the coupon,
// books lifetime spend, then audits and emails.
export function checkout(orderId) {
  const order = loadOrder(orderId);
  if (order.status !== "open") throw `bad_state: order ${orderId} is ${order.status}`;
  if (order.items.length === 0) throw "invalid: order has no items";
  const customer = getCustomer(order.customerId);
  if (!customer) throw `not_found: unknown customer ${order.customerId}`;

  computeTotal(order);
  if (order.couponCode) {
    const coupon = getCoupon(order.couponCode);
    if (!coupon) throw `coupon_invalid: unknown coupon ${order.couponCode}`;
    const bad = checkCoupon(coupon, order.pricing.subtotalCents);
    if (bad) throw bad;
  }

  const short = reserve(order.items);
  if (short !== -1) {
    record("checkout_failed", orderId, "out_of_stock");
    throw `out_of_stock: not enough stock for ${order.items[short].sku}`;
  }
  if (order.couponCode) recordCouponUse(order.couponCode);

  order.status = "paid";
  order.paidAt = state.clock.now();
  adjustSpend(customer.id, order.pricing.totalCents);
  record("checkout", orderId, String(order.pricing.totalCents));
  queueEmail(customer, "order_confirmation", orderId);
  return order;
}

export function ordersFor(customerId) {
  return [...state.db.orders.values()].filter((o) => o.customerId === customerId);
}

export function openOrders() {
  return [...state.db.orders.values()].filter((o) => o.status === "open");
}

// One-line summary for logs and support tooling.
export function describeOrder(order) {
  const parts = order.items.map((i) => `${i.qty}x ${i.sku}`);
  const total = formatCents(order.pricing.totalCents);
  return `${order.id} [${order.status}] ${parts.join(", ") || "empty"} = ${total}`;
}
