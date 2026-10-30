import type {
  Cents, Config, Coupon, Ctx, Customer, Db, DiscountLine, Pricing, Result, VipTier,
} from "./types.ts";
import { err, ok } from "./types.ts";
import { isCents, percentOf, sumCents } from "./money.ts";
import { tierOf } from "./customers.ts";
import { taxFor } from "./tax.ts";
import { shippingFor } from "./shipping.ts";

// ---- priced lines ----

export interface PricedLine {
  sku: string;
  qty: number;
  unitPriceCents: Cents;
  lineCents: Cents;
  weightG: number;
  taxable: boolean;
  category: string;
}

export const zeroPricing: Pricing = {
  subtotalCents: 0,
  discounts: [],
  discountCents: 0,
  taxableCents: 0,
  taxCents: 0,
  shippingCents: 0,
  totalCents: 0,
};

// ---- discount rules (an explicit, ordered registry passed to every pricing call) ----

export interface RuleInput {
  config: Config;
  tier: VipTier;
  lines: readonly PricedLine[];
  coupon: Coupon | null;
  /** subtotal minus the discounts granted by earlier rules */
  remainingCents: Cents;
}

export interface DiscountRule {
  name: string;
  /** Returns the discount in cents (clamped to remainingCents by the caller). */
  apply(input: RuleInput): Cents;
}

export type RuleRegistry = readonly DiscountRule[];

export const bulkRule: DiscountRule = {
  name: "bulk",
  apply({ config, lines }) {
    let total = 0;
    for (const line of lines) {
      if (line.qty >= config.bulkQty) total += percentOf(line.lineCents, config.bulkBps);
    }
    return total;
  },
};

export const vipRule: DiscountRule = {
  name: "vip",
  apply({ tier, coupon, remainingCents }) {
    if (coupon && !coupon.stackable) return 0;
    return percentOf(remainingCents, tier.discountBps);
  },
};

export const couponRule: DiscountRule = {
  name: "coupon",
  apply({ coupon, remainingCents }) {
    if (!coupon) return 0;
    if (coupon.kind === "percent") return percentOf(remainingCents, coupon.value);
    return Math.min(coupon.value, remainingCents);
  },
};

/** Order matters: each rule sees what the previous ones left. */
export function defaultRules(): RuleRegistry {
  return [bulkRule, vipRule, couponRule];
}

/** Runs the registry in order. Pure. */
export function computeDiscounts(
  config: Config,
  rules: RuleRegistry,
  tier: VipTier,
  lines: readonly PricedLine[],
  coupon: Coupon | null,
  subtotalCents: Cents,
): DiscountLine[] {
  const out: DiscountLine[] = [];
  let remaining = subtotalCents;
  for (const rule of rules) {
    const raw = rule.apply({ config, tier, lines, coupon, remainingCents: remaining });
    const amount = Math.max(0, Math.min(raw, remaining));
    if (amount > 0) {
      out.push({ rule: rule.name, amountCents: amount });
      remaining -= amount;
    }
  }
  return out;
}

// ---- the full price of an order ----

export interface PriceInput {
  customer: Customer;
  shipRegion: string;
  lines: readonly PricedLine[];
  coupon: Coupon | null;
}

/** Pure: subtotal -> discounts -> tax (on discounted taxable goods) -> shipping -> total. */
export function priceOrder(config: Config, rules: RuleRegistry, input: PriceInput): Pricing {
  const { customer, shipRegion, lines, coupon } = input;
  const tier = tierOf(config, customer);
  const subtotalCents = sumCents(lines.map((l) => l.lineCents));
  const discounts = computeDiscounts(config, rules, tier, lines, coupon, subtotalCents);
  const discountCents = sumCents(discounts.map((d) => d.amountCents));
  const goodsCents = subtotalCents - discountCents;

  const taxableSub = sumCents(lines.filter((l) => l.taxable).map((l) => l.lineCents));
  const taxableDiscount = subtotalCents === 0 ? 0 : Math.round((discountCents * taxableSub) / subtotalCents);
  const taxableCents = taxableSub - taxableDiscount;
  const taxCents = taxFor(config, shipRegion, taxableCents);

  const weightG = lines.reduce((w, l) => w + l.weightG * l.qty, 0);
  const shippingCents = shippingFor(config, tier, weightG, goodsCents);

  return {
    subtotalCents,
    discounts,
    discountCents,
    taxableCents,
    taxCents,
    shippingCents,
    totalCents: goodsCents + taxCents + shippingCents,
  };
}

// ---- coupons ----

export interface CouponInput {
  code: string;
  kind: "percent" | "fixed";
  value: number;
  stackable?: boolean;
  minSubtotalCents?: Cents;
  maxUses?: number | null;
  expiresAt?: number | null;
}

export function addCoupon(db: Db, input: CouponInput): Result<Coupon> {
  if (!input.code) return err("invalid", "code required");
  if (db.coupons.has(input.code)) return err("duplicate", `coupon ${input.code} exists`);
  if (input.kind === "percent") {
    if (!Number.isInteger(input.value) || input.value < 1 || input.value > 10000) {
      return err("invalid", "percent value is basis points, 1..10000");
    }
  } else if (input.kind === "fixed") {
    if (!isCents(input.value) || input.value === 0) return err("invalid", "fixed value must be positive cents");
  } else {
    return err("invalid", "kind must be percent or fixed");
  }
  const coupon: Coupon = {
    code: input.code,
    kind: input.kind,
    value: input.value,
    stackable: input.stackable ?? true,
    minSubtotalCents: input.minSubtotalCents ?? 0,
    maxUses: input.maxUses ?? null,
    expiresAt: input.expiresAt ?? null,
  };
  db.coupons.set(coupon.code, coupon);
  return ok(coupon);
}

export function getCoupon(db: Db, code: string): Coupon | undefined {
  return db.coupons.get(code);
}

export function couponUses(db: Db, code: string): number {
  return db.couponUses.get(code) ?? 0;
}

/** Counts one redemption of `code` in `db.couponUses`. */
export function recordCouponUse(db: Db, code: string): void {
  db.couponUses.set(code, couponUses(db, code) + 1);
}

/** Whether `coupon` may be redeemed now against an order with this undiscounted subtotal. */
export function checkCoupon(ctx: Ctx, coupon: Coupon, subtotalCents: Cents): Result<Coupon> {
  if (coupon.expiresAt !== null && ctx.clock.now() >= coupon.expiresAt) {
    return err("coupon_expired", `coupon ${coupon.code} expired`);
  }
  if (coupon.maxUses !== null && couponUses(ctx.db, coupon.code) >= coupon.maxUses) {
    return err("coupon_exhausted", `coupon ${coupon.code} has no uses left`);
  }
  if (subtotalCents < coupon.minSubtotalCents) {
    return err("coupon_invalid", `coupon ${coupon.code} needs a larger subtotal`);
  }
  return ok(coupon);
}
