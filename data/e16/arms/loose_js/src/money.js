export function isCents(n) {
  return Number.isInteger(+n) && +n >= 0;
}

// `bps` basis points of `cents`, rounded half up to a whole cent.
export function percentOf(cents, bps) {
  return Math.round((cents * bps) / 10000);
}

export function sumCents(values) {
  let total = 0;
  for (const v of values) total += v;
  return total;
}

export function clamp(n, lo, hi) {
  return Math.max(lo, Math.min(hi, n));
}

export function formatCents(cents) {
  const whole = Math.floor(cents / 100);
  const frac = String(cents % 100).padStart(2, "0");
  return whole + "." + frac;
}

export function maxCents(values) {
  let best = 0;
  for (const v of values) if (v > best) best = v;
  return best;
}
