import type { Db, Product, Result } from "./types.ts";
import { err, ok } from "./types.ts";
import { isCents } from "./money.ts";

export interface ProductInput {
  sku: string;
  name: string;
  priceCents: number;
  weightG?: number;
  taxable?: boolean;
  category?: string;
}

/** Adds a product to `db.products`. */
export function addProduct(db: Db, input: ProductInput): Result<Product> {
  if (!input.sku) return err("invalid", "sku required");
  if (db.products.has(input.sku)) return err("duplicate", `product ${input.sku} exists`);
  if (!isCents(input.priceCents)) return err("invalid", "priceCents must be a non-negative integer");
  const weightG = input.weightG ?? 0;
  if (!Number.isInteger(weightG) || weightG < 0) return err("invalid", "weightG must be a non-negative integer");
  const product: Product = {
    sku: input.sku,
    name: input.name,
    priceCents: input.priceCents,
    weightG,
    taxable: input.taxable ?? true,
    category: input.category ?? "general",
  };
  db.products.set(product.sku, product);
  return ok(product);
}

export function getProduct(db: Db, sku: string): Product | undefined {
  return db.products.get(sku);
}

export function listProducts(db: Db): Product[] {
  return [...db.products.values()].sort((a, b) => a.sku.localeCompare(b.sku));
}
