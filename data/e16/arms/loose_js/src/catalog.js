import { state } from "./state.js";
import { isCents } from "./money.js";

export function addProduct(input) {
  if (!input.sku) throw "invalid: sku required";
  if (state.db.products.has(input.sku)) throw `duplicate: product ${input.sku} exists`;
  if (!isCents(input.priceCents)) throw "invalid: priceCents must be a non-negative integer";
  const weightG = +input.weightG || 0;
  if (!Number.isInteger(weightG) || weightG < 0) throw "invalid: weightG must be a non-negative integer";
  const product = {
    sku: input.sku,
    name: input.name,
    priceCents: +input.priceCents,
    weightG,
    taxable: input.taxable !== false,
    category: input.category || "general",
  };
  state.db.products.set(product.sku, product);
  return product;
}

export function getProduct(sku) {
  return state.db.products.get(sku) || null;
}

export function listProducts() {
  return [...state.db.products.values()].sort((a, b) => a.sku.localeCompare(b.sku));
}

// Joins order items with catalog data.
export function buildLines(items) {
  return items.map((item) => {
    const product = getProduct(item.sku);
    if (!product) throw `not_found: unknown sku ${item.sku}`;
    return {
      sku: item.sku,
      qty: item.qty,
      unitPriceCents: item.unitPriceCents,
      lineCents: item.unitPriceCents * item.qty,
      weightG: product.weightG,
      taxable: product.taxable,
      category: product.category,
    };
  });
}

export function productsInCategory(category) {
  return listProducts().filter((p) => p.category === category);
}

// Case-insensitive match on sku or name.
export function findProducts(query) {
  const q = String(query || "").toLowerCase();
  return listProducts().filter((p) => p.sku.toLowerCase().includes(q) || p.name.toLowerCase().includes(q));
}
