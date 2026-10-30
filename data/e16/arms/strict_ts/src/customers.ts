import type { Config, Ctx, Customer, Db, Cents, Result, VipTier } from "./types.ts";
import { err, ok } from "./types.ts";

export interface CustomerInput {
  id: string;
  name: string;
  email: string;
  region: string;
}

export function addCustomer(ctx: Ctx, input: CustomerInput): Result<Customer> {
  if (!input.id || !input.name) return err("invalid", "id and name required");
  if (ctx.db.customers.has(input.id)) return err("duplicate", `customer ${input.id} exists`);
  const customer: Customer = {
    id: input.id,
    name: input.name,
    email: input.email,
    region: input.region || ctx.config.defaultRegion,
    lifetimeSpendCents: 0,
  };
  ctx.db.customers.set(customer.id, customer);
  return ok(customer);
}

export function getCustomer(db: Db, id: string): Customer | undefined {
  return db.customers.get(id);
}

/** Highest tier whose spend threshold is met. Pure. */
export function tierFor(config: Config, spendCents: Cents): VipTier {
  let best = config.vipTiers[0];
  for (const tier of config.vipTiers) {
    if (spendCents >= tier.minSpendCents) best = tier;
  }
  return best;
}

export function tierOf(config: Config, customer: Customer): VipTier {
  return tierFor(config, customer.lifetimeSpendCents);
}

/** Adds `deltaCents` (may be negative) to the stored customer's lifetime spend, never below 0. */
export function adjustSpend(db: Db, id: string, deltaCents: Cents): void {
  const c = db.customers.get(id);
  if (!c) return;
  db.customers.set(id, { ...c, lifetimeSpendCents: Math.max(0, c.lifetimeSpendCents + deltaCents) });
}
