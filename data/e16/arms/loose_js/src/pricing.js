import { state } from "./state.js";
import { isCents, percentOf, sumCents } from "./money.js";
import { getCustomer, tierOf } from "./customers.js";
import { taxFor } from "./tax.js";
import { shippingFor } from "./shipping.js";
import { buildLines } from "./catalog.js";

// ---- discount rules ----

export const ruleRegistry = [];

export function registerRule(name, apply) {
  ruleRegistry.push({ name, apply });
}

// Each rule sees what the previous ones left.
function applyRules(order, lines, tier) {
  const p = order.pricing;
  let remaining = p.subtotalCents;
  for (const rule of state.rules) {
    const raw = rule.apply({ order, lines, tier, remaining });
    const amount = Math.max(0, Math.min(raw, remaining));
    if (amount > 0) {
      p.discounts.push({ rule: rule.name, amountCents: amount });
      remaining -= amount;
    }
  }
  p.discountCents = sumCents(p.discounts.map((d) => d.amountCents));
}

// ---- the full price of an order ----

// Splits the goods part of the total (everything but shipping) across lines, proportional to line value.
function allocateLineNet(p, lines) {
  const goods = p.totalCents - p.shippingCents;
  const out = {};
  let allocated = 0;
  lines.forEach((line, i) => {
    const share = i === lines.length - 1
      ? goods - allocated
      : p.subtotalCents === 0 ? 0 : Math.round((goods * line.lineCents) / p.subtotalCents);
    out[line.sku] = share;
    allocated += share;
  });
  return out;
}

// subtotal -> discounts -> tax (on discounted taxable goods) -> shipping -> total
export function computeTotal(order) {
  const customer = getCustomer(order.customerId);
  if (!customer) throw `not_found: unknown customer ${order.customerId}`;
  const lines = buildLines(order.items);
  const tier = tierOf(customer);
  const p = order.pricing = {
    subtotalCents: sumCents(lines.map((l) => l.lineCents)),
    discounts: [],
    discountCents: 0,
    taxableCents: 0,
    taxCents: 0,
    shippingCents: 0,
    totalCents: 0,
  };
  applyRules(order, lines, tier);

  const taxableSub = sumCents(lines.filter((l) => l.taxable).map((l) => l.lineCents));
  const taxableDiscount = p.subtotalCents ? Math.round((p.discountCents * taxableSub) / p.subtotalCents) : 0;
  p.taxableCents = taxableSub - taxableDiscount;
  p.taxCents = taxFor(order.shipRegion, p.taxableCents);

  const weightG = lines.reduce((w, l) => w + l.weightG * l.qty, 0);
  p.shippingCents = shippingFor(order, tier, weightG);
  p.totalCents = p.subtotalCents - p.discountCents + p.taxCents + p.shippingCents;
  order.lineNetCents = allocateLineNet(p, lines);
  return p.totalCents;
}

// ---- coupons ----

export function addCoupon(input) {
  if (!input.code) throw "invalid: code required";
  if (state.db.coupons.has(input.code)) throw `duplicate: coupon ${input.code} exists`;
  if (input.kind === "percent") {
    if (!Number.isInteger(input.value) || input.value < 1 || input.value > 10000) {
      throw "invalid: percent value is basis points, 1..10000";
    }
  } else if (input.kind === "fixed") {
    if (!isCents(input.value) || +input.value === 0) throw "invalid: fixed value must be positive cents";
  } else {
    throw "invalid: kind must be percent or fixed";
  }
  const coupon = {
    code: input.code,
    kind: input.kind,
    value: +input.value,
    stackable: input.stackable !== false,
    minSubtotalCents: input.minSubtotalCents || 0,
    maxUses: input.maxUses == null ? null : input.maxUses,
    expiresAt: input.expiresAt == null ? null : input.expiresAt,
  };
  state.db.coupons.set(coupon.code, coupon);
  return coupon;
}

export function getCoupon(code) {
  return state.db.coupons.get(code) || null;
}

export function couponUses(code) {
  return state.db.couponUses.get(code) || 0;
}

// Counts one redemption of `code`.
export function recordCouponUse(code) {
  state.db.couponUses.set(code, couponUses(code) + 1);
}

// Returns null when `coupon` may be redeemed now against this undiscounted subtotal,
// otherwise a "code: message" string.
export function checkCoupon(coupon, subtotalCents) {
  if (coupon.expiresAt !== null && state.clock.now() >= coupon.expiresAt) {
    return `coupon_expired: coupon ${coupon.code} expired`;
  }
  if (coupon.maxUses !== null && couponUses(coupon.code) >= coupon.maxUses) {
    return `coupon_exhausted: coupon ${coupon.code} has no uses left`;
  }
  if (subtotalCents < coupon.minSubtotalCents) {
    return `coupon_invalid: coupon ${coupon.code} needs a larger subtotal`;
  }
  return null;
}

export function listCoupons() {
  return [...state.db.coupons.values()].sort((a, b) => a.code.localeCompare(b.code));
}

// Coupons that still have uses left and have not expired.
export function activeCoupons() {
  return listCoupons().filter((c) => {
    if (c.expiresAt !== null && state.clock.now() >= c.expiresAt) return false;
    return c.maxUses === null || couponUses(c.code) < c.maxUses;
  });
}

export function describeDiscounts(order) {
  return order.pricing.discounts.map((d) => `${d.rule}: ${d.amountCents}`).join("; ");
}
