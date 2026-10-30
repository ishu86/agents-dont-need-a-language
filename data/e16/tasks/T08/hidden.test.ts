import { createShop } from "__ENTRY__";

// ---- tiny local assert helpers (hidden tests are copied alone, so they are inlined) ----
function eq(actual: unknown, expected: unknown, msg = "") {
  if (JSON.stringify(actual) !== JSON.stringify(expected)) {
    throw new Error(`${msg} expected ${JSON.stringify(expected)}, got ${JSON.stringify(actual)}`);
  }
}
// deno-lint-ignore no-explicit-any
function must(r: any): any {
  if (!r.ok) throw new Error(`unexpected error: ${JSON.stringify(r.error)}`);
  return r.value;
}
// deno-lint-ignore no-explicit-any
function code(r: any): string {
  if (r.ok) throw new Error("expected an error result");
  return r.error.code;
}

// Fixture: products pen/book/lamp/mug/oldmug/gem, customers alice(CA) bob(NY) carol(OR), clock fixed at 1000.
function setup(opts: Record<string, unknown> = {}) {
  const t = { now: 1000 };
  const shop = createShop({ now: () => t.now, ...opts });
  shop.addProduct({ sku: "pen", name: "Pen", priceCents: 200, weightG: 20, taxable: true, category: "office" });
  shop.addProduct({ sku: "book", name: "Book", priceCents: 1500, weightG: 400, taxable: false, category: "books" });
  shop.addProduct({ sku: "lamp", name: "Lamp", priceCents: 4000, weightG: 1500, taxable: true, category: "home" });
  shop.addProduct({ sku: "mug", name: "Mug", priceCents: 800, weightG: 300, taxable: true, category: "home" });
  shop.addProduct({ sku: "oldmug", name: "Old Mug", priceCents: 1000, weightG: 300, taxable: true, category: "clearance" });
  shop.addProduct({ sku: "gem", name: "Gem", priceCents: 20000, weightG: 0, taxable: false, category: "luxury" });
  for (const sku of ["pen", "book", "lamp", "mug", "oldmug"]) shop.addStock(sku, 20);
  shop.addStock("gem", 20);
  shop.addCustomer({ id: "alice", name: "Alice", email: "alice@example.com", region: "CA" });
  shop.addCustomer({ id: "bob", name: "Bob", email: "bob@example.com", region: "NY" });
  shop.addCustomer({ id: "carol", name: "Carol", email: "carol@example.com", region: "OR" });
  return { shop, t };
}
type Shop = ReturnType<typeof setup>["shop"];

function order(shop: Shop, customerId: string, items: Array<[string, number]>, shipRegion?: string) {
  const o = must(shop.createOrder(shipRegion ? { customerId, shipRegion } : { customerId }));
  for (const [sku, qty] of items) must(shop.addItem(o.id, sku, qty));
  return o.id as string;
}
function makeSilver(shop: Shop, id = "carol") {
  must(shop.checkout(order(shop, id, [["gem", 1]])));
}
function makeGold(shop: Shop, id = "carol") {
  must(shop.checkout(order(shop, id, [["gem", 5]])));
}

// ---- tests ----
Deno.test("points: earned at checkout, taken back on refund", () => {
  const { shop } = setup();
  eq(shop.points("alice"), 0);
  eq(shop.points("ghost"), undefined);
  const id = order(shop, "alice", [["mug", 2]]);
  must(shop.checkout(id));
  eq(shop.points("alice"), 23);
  must(shop.refund(id, [{ sku: "mug", qty: 1 }]));
  eq(shop.points("alice"), 15);
  must(shop.refund(id));
  eq(shop.points("alice"), 0);
});

Deno.test("points: failed checkout earns nothing", () => {
  const { shop } = setup();
  const id = order(shop, "alice", [["pen", 30]]);
  eq(code(shop.checkout(id)), "out_of_stock");
  eq(shop.points("alice"), 0);
});

Deno.test("points: gold doubles, using the tier held before the order", () => {
  const { shop } = setup();
  makeGold(shop);
  eq(shop.tier("carol"), "gold");
  eq(shop.points("carol"), 1000);
  const id = order(shop, "carol", [["lamp", 1]]);
  const o = must(shop.checkout(id));
  eq(o.pricing.totalCents, 3600);
  eq(shop.points("carol"), 1000 + 72);
  must(shop.refund(id));
  eq(shop.points("carol"), 1000);
});

Deno.test("points: refund uses the multiplier from purchase time", () => {
  const { shop } = setup();
  const lamp = order(shop, "carol", [["lamp", 1]]);
  must(shop.checkout(lamp));
  eq(shop.points("carol"), 48);
  makeGold(shop);
  eq(shop.points("carol"), 1048);
  must(shop.refund(lamp));
  eq(shop.points("carol"), 1000);
});
