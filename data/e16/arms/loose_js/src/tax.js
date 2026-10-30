import { state } from "./state.js";
import { percentOf } from "./money.js";

// Tax rate in basis points for a region; unknown regions are untaxed.
export function rateBps(region) {
  return state.config.taxBpsByRegion[region] || 0;
}

export function taxFor(region, taxableCents) {
  return percentOf(taxableCents, rateBps(region));
}
