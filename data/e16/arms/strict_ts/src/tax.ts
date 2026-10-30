import type { Cents, Config } from "./types.ts";
import { percentOf } from "./money.ts";

/** Tax rate in basis points for a region; unknown regions are untaxed. */
export function rateBps(config: Config, region: string): number {
  return config.taxBpsByRegion[region] ?? 0;
}

export function taxFor(config: Config, region: string, taxableCents: Cents): Cents {
  return percentOf(taxableCents, rateBps(config, region));
}
