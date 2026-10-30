export function isCents(n: any): boolean {
  return Number.isInteger(+n) && +n >= 0;
}

// `bps` basis points of `cents`, rounded half up to a whole cent.
export function percentOf(cents: number, bps: number): number {
  return Math.round((cents * bps) / 10000);
}

export function sumCents(values: number[]): number {
  let total = 0;
  for (const v of values) total += v;
  return total;
}

export function clamp(n: number, lo: number, hi: number): number {
  return Math.max(lo, Math.min(hi, n));
}

export function formatCents(cents: number): string {
  const whole = Math.floor(cents / 100);
  const frac = String(cents % 100).padStart(2, "0");
  return whole + "." + frac;
}

export function maxCents(values: number[]): number {
  let best = 0;
  for (const v of values) if (v > best) best = v;
  return best;
}
