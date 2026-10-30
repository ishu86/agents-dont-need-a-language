import { state } from "./state.ts";
import { percentOf } from "./money.ts";

// Tax rate in basis points for a region; unknown regions are untaxed.
export function rateBps(region: string): number {
  return state.config.taxBpsByRegion[region] || 0;
}

export function taxFor(region: string, taxableCents: number): number {
  return percentOf(taxableCents, rateBps(region));
}
