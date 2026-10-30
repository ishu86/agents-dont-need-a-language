import type { Cents, Config, VipTier } from "./types.ts";

/**
 * Shipping charge. Zero for weightless (digital) orders, tiers with free shipping,
 * and orders whose goods value `goodsCents` reaches the free-shipping threshold.
 * Otherwise base + per-kg for each started kg.
 */
export function shippingFor(
  config: Config,
  tier: VipTier,
  totalWeightG: number,
  goodsCents: Cents,
): Cents {
  if (totalWeightG === 0) return 0;
  if (tier.freeShipping) return 0;
  if (goodsCents >= config.freeShippingThresholdCents) return 0;
  return config.shippingBaseCents + config.shippingPerKgCents * Math.ceil(totalWeightG / 1000);
}
