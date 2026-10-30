import type { Cents, Ctx, Db, Order, OrderItem, Pricing, Result } from "./types.ts";
import { err, ok } from "./types.ts";
import { getCustomer, adjustSpend } from "./customers.ts";
import { getProduct } from "./catalog.ts";
import { reserve } from "./inventory.ts";
import {
  checkCoupon, getCoupon, priceOrder, recordCouponUse, zeroPricing,
  type PricedLine, type RuleRegistry,
} from "./pricing.ts";
import { record } from "./audit.ts";
import { queueEmail } from "./notifications.ts";
import { nextOrderId } from "./storage.ts";

export function getOrder(db: Db, id: string): Order | undefined {
  return db.orders.get(id);
}

function loadOrder(db: Db, id: string): Result<Order> {
  const order = db.orders.get(id);
  return order ? ok(order) : err("not_found", `unknown order ${id}`);
}

function saveOrder(db: Db, order: Order): Order {
  db.orders.set(order.id, order);
  return order;
}

/** Joins order items with catalog data. */
export function buildLines(db: Db, items: readonly OrderItem[]): Result<PricedLine[]> {
  const lines: PricedLine[] = [];
  for (const item of items) {
    const product = getProduct(db, item.sku);
    if (!product) return err("not_found", `unknown sku ${item.sku}`);
    lines.push({
      sku: item.sku,
      qty: item.qty,
      unitPriceCents: item.unitPriceCents,
      lineCents: item.unitPriceCents * item.qty,
      weightG: product.weightG,
      taxable: product.taxable,
      category: product.category,
    });
  }
  return ok(lines);
}

/** Returns `order` with `pricing` recomputed from its current items, coupon and customer. Does not save. */
export function repriced(ctx: Ctx, rules: RuleRegistry, order: Order): Result<Order> {
  const customer = getCustomer(ctx.db, order.customerId);
  if (!customer) return err("not_found", `unknown customer ${order.customerId}`);
  const lines = buildLines(ctx.db, order.items);
  if (!lines.ok) return lines;
  const coupon = order.couponCode ? getCoupon(ctx.db, order.couponCode) ?? null : null;
  const pricing = priceOrder(ctx.config, rules, {
    customer,
    shipRegion: order.shipRegion,
    lines: lines.value,
    coupon,
  });
  return ok({ ...order, pricing });
}

export interface CreateOrderInput {
  customerId: string;
  shipRegion?: string;
}

export function createOrder(ctx: Ctx, input: CreateOrderInput): Result<Order> {
  const customer = getCustomer(ctx.db, input.customerId);
  if (!customer) return err("not_found", `unknown customer ${input.customerId}`);
  const order: Order = {
    id: nextOrderId(ctx.db),
    customerId: customer.id,
    shipRegion: input.shipRegion ?? customer.region,
    items: [],
    couponCode: null,
    status: "open",
    pricing: zeroPricing,
    lineNetCents: {},
    refundedByLine: {},
    refundedCents: 0,
    createdAt: ctx.clock.now(),
    paidAt: null,
  };
  saveOrder(ctx.db, order);
  record(ctx.log, ctx.clock, "order_created", order.id, customer.id);
  return ok(order);
}

export function addItem(
  ctx: Ctx,
  rules: RuleRegistry,
  orderId: string,
  sku: string,
  qty: number,
): Result<Order> {
  const loaded = loadOrder(ctx.db, orderId);
  if (!loaded.ok) return loaded;
  const order = loaded.value;
  if (order.status !== "open") return err("bad_state", `order ${orderId} is ${order.status}`);
  const product = getProduct(ctx.db, sku);
  if (!product) return err("not_found", `unknown sku ${sku}`);
  if (!Number.isInteger(qty) || qty <= 0) return err("invalid", "qty must be a positive integer");

  const existing = order.items.find((i) => i.sku === sku);
  const items: OrderItem[] = existing
    ? order.items.map((i) => (i.sku === sku ? { ...i, qty: i.qty + qty } : i))
    : [...order.items, { sku, qty, unitPriceCents: product.priceCents }];
  const next = repriced(ctx, rules, { ...order, items });
  if (!next.ok) return next;
  return ok(saveOrder(ctx.db, next.value));
}

export function applyCoupon(ctx: Ctx, rules: RuleRegistry, orderId: string, code: string): Result<Order> {
  const loaded = loadOrder(ctx.db, orderId);
  if (!loaded.ok) return loaded;
  const order = loaded.value;
  if (order.status !== "open") return err("bad_state", `order ${orderId} is ${order.status}`);
  const coupon = getCoupon(ctx.db, code);
  if (!coupon) return err("coupon_invalid", `unknown coupon ${code}`);
  const usable = checkCoupon(ctx, coupon, order.pricing.subtotalCents);
  if (!usable.ok) return usable;
  const next = repriced(ctx, rules, { ...order, couponCode: code });
  if (!next.ok) return next;
  record(ctx.log, ctx.clock, "coupon_applied", orderId, code);
  return ok(saveOrder(ctx.db, next.value));
}

/** Splits the goods part of the total (everything but shipping) across lines, proportional to line value. */
export function allocateLineNet(pricing: Pricing, lines: readonly PricedLine[]): Record<string, Cents> {
  const goods = pricing.totalCents - pricing.shippingCents;
  const out: Record<string, Cents> = {};
  let allocated = 0;
  lines.forEach((line, i) => {
    const isLast = i === lines.length - 1;
    const share = isLast
      ? goods - allocated
      : pricing.subtotalCents === 0
      ? 0
      : Math.round((goods * line.lineCents) / pricing.subtotalCents);
    out[line.sku] = share;
    allocated += share;
  });
  return out;
}

/**
 * Pays an open order: reprices, validates the coupon, reserves stock, redeems the coupon,
 * books lifetime spend, then audits and emails.
 */
export function checkout(ctx: Ctx, rules: RuleRegistry, orderId: string): Result<Order> {
  const loaded = loadOrder(ctx.db, orderId);
  if (!loaded.ok) return loaded;
  const order = loaded.value;
  if (order.status !== "open") return err("bad_state", `order ${orderId} is ${order.status}`);
  if (order.items.length === 0) return err("invalid", "order has no items");
  const customer = getCustomer(ctx.db, order.customerId);
  if (!customer) return err("not_found", `unknown customer ${order.customerId}`);

  const fresh = repriced(ctx, rules, order);
  if (!fresh.ok) return fresh;
  const priced = fresh.value;

  if (priced.couponCode) {
    const coupon = getCoupon(ctx.db, priced.couponCode);
    if (!coupon) return err("coupon_invalid", `unknown coupon ${priced.couponCode}`);
    const usable = checkCoupon(ctx, coupon, priced.pricing.subtotalCents);
    if (!usable.ok) return usable;
  }

  const reserved = reserve(ctx.db, priced.items);
  if (!reserved.ok) {
    record(ctx.log, ctx.clock, "checkout_failed", orderId, reserved.error.code);
    return reserved;
  }
  if (priced.couponCode) recordCouponUse(ctx.db, priced.couponCode);

  const lines = buildLines(ctx.db, priced.items);
  if (!lines.ok) return lines;
  const paid: Order = {
    ...priced,
    status: "paid",
    lineNetCents: allocateLineNet(priced.pricing, lines.value),
    paidAt: ctx.clock.now(),
  };
  saveOrder(ctx.db, paid);
  adjustSpend(ctx.db, customer.id, paid.pricing.totalCents);
  record(ctx.log, ctx.clock, "checkout", orderId, String(paid.pricing.totalCents));
  queueEmail(ctx, customer, "order_confirmation", orderId);
  return ok(paid);
}
