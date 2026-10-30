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
Deno.test("cancelOrder: open order", () => {
  const { shop } = setup();
  const id = order(shop, "alice", [["pen", 2]]);
  const o = must(shop.cancelOrder(id));
  eq(o.status, "cancelled");
  eq(shop.getOrder(id)!.status, "cancelled");
  eq(shop.stock("pen"), 20);
  eq(shop.audit().filter((e) => e.action === "order_cancelled").map((e) => e.subjectId), [id]);
  eq(shop.outbox().map((m) => m.template), ["order_cancelled"]);
  eq(code(shop.cancelOrder(id)), "bad_state");
  eq(code(shop.checkout(id)), "bad_state");
  eq(code(shop.addItem(id, "pen", 1)), "bad_state");
  eq(code(shop.cancelOrder("ord_404")), "not_found");
});

Deno.test("cancelOrder: paid order is refunded in full", () => {
  const { shop } = setup();
  const id = order(shop, "alice", [["mug", 2]]);
  must(shop.checkout(id));
  const o = must(shop.cancelOrder(id));
  eq(o.status, "cancelled");
  eq(o.refundedCents, 2378);
  eq(shop.stock("mug"), 20);
  eq(shop.getCustomer("alice")!.lifetimeSpendCents, 0);
  eq(shop.audit().filter((e) => e.subjectId === id).map((e) => e.action), ["order_created", "checkout", "refund", "order_cancelled"]);
  eq(shop.outbox().map((m) => m.template), ["order_confirmation", "refund_issued", "order_cancelled"]);
  eq(code(shop.refund(id)), "bad_state");
});

Deno.test("cancelOrder: partly refunded order refunds only the rest", () => {
  const { shop } = setup();
  const id = order(shop, "alice", [["mug", 2]]);
  must(shop.checkout(id));
  must(shop.refund(id, [{ sku: "mug", qty: 1 }]));
  const o = must(shop.cancelOrder(id));
  eq(o.status, "cancelled");
  eq(o.refundedCents, 2378);
  eq(shop.stock("mug"), 20);
  const refunds = shop.audit().filter((e) => e.action === "refund").map((e) => e.detail);
  eq(refunds, ["864", "1514"]);
});

Deno.test("cancelOrder: refunded orders cannot be cancelled", () => {
  const { shop } = setup();
  const id = order(shop, "alice", [["pen", 1]]);
  must(shop.checkout(id));
  must(shop.refund(id));
  eq(code(shop.cancelOrder(id)), "bad_state");
});
