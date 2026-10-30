import { state } from "./state.ts";

export function addCustomer(input: any): any {
  if (!input.id || !input.name) throw "invalid: id and name required";
  if (state.db.customers.has(input.id)) throw `duplicate: customer ${input.id} exists`;
  const customer = {
    id: input.id,
    name: input.name,
    email: input.email,
    region: input.region || state.config.defaultRegion,
    lifetimeSpendCents: 0,
  };
  state.db.customers.set(customer.id, customer);
  return customer;
}

export function getCustomer(id: string): any {
  return state.db.customers.get(id) || null;
}

// Highest tier whose spend threshold is met.
export function tierFor(spendCents: number): any {
  let best = state.config.vipTiers[0];
  for (const tier of state.config.vipTiers) {
    if (spendCents >= tier.minSpendCents) best = tier;
  }
  return best;
}

export function tierOf(customer: any): any {
  return tierFor(customer.lifetimeSpendCents);
}

// Adds `deltaCents` (may be negative) to a customer's lifetime spend, never below 0.
export function adjustSpend(id: string, deltaCents: number): void {
  const c = getCustomer(id);
  if (!c) return;
  c.lifetimeSpendCents = Math.max(0, c.lifetimeSpendCents + deltaCents);
}

export function listCustomers(): any[] {
  return [...state.db.customers.values()].sort((a: any, b: any) => a.id.localeCompare(b.id));
}

// Cents of lifetime spend still needed to reach the next tier, or 0 at the top.
export function spendToNextTier(customer: any): number {
  const tiers = state.config.vipTiers;
  const next = tiers.find((t: any) => t.minSpendCents > customer.lifetimeSpendCents);
  return next ? next.minSpendCents - customer.lifetimeSpendCents : 0;
}

export function customersInTier(name: string): any[] {
  return listCustomers().filter((c: any) => tierOf(c).name === name);
}
