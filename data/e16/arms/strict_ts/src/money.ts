import type { Cents } from "./types.ts";

export function isCents(n: unknown): n is Cents {
  return typeof n === "number" && Number.isInteger(n) && n >= 0;
}

/** `bps` basis points of `cents`, rounded half up to a whole cent. */
export function percentOf(cents: Cents, bps: number): Cents {
  return Math.round((cents * bps) / 10000);
}

export function sumCents(values: readonly Cents[]): Cents {
  let total = 0;
  for (const v of values) total += v;
  return total;
}

export function clamp(n: number, lo: number, hi: number): number {
  return Math.max(lo, Math.min(hi, n));
}

export function formatCents(cents: Cents): string {
  const whole = Math.floor(cents / 100);
  const frac = String(cents % 100).padStart(2, "0");
  return `${whole}.${frac}`;
}
