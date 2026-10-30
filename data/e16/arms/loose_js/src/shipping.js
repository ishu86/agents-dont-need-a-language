import { state } from "./state.js";

// Shipping charge. Zero for weightless (digital) orders, tiers with free shipping,
// and orders whose goods value reaches the free-shipping threshold.
// Otherwise base + per-kg for each started kg.
export function shippingFor(order, tier, totalWeightG) {
  const p = order.pricing;
  const goods = p.subtotalCents - p.discountCents;
  if (!totalWeightG) return 0;
  if (tier.freeShipping) return 0;
  if (goods >= state.config.freeShippingThresholdCents) return 0;
  return state.config.shippingBaseCents + state.config.shippingPerKgCents * Math.ceil(totalWeightG / 1000);
}
