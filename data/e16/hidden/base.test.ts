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

Deno.test("catalog and customers: validation", () => {
  const { shop } = setup();
  eq(code(shop.addProduct({ sku: "pen", name: "x", priceCents: 1 })), "duplicate");
  eq(code(shop.addProduct({ sku: "bad", name: "x", priceCents: 1.5 })), "invalid");
  eq(code(shop.addProduct({ sku: "neg", name: "x", priceCents: -1 })), "invalid");
  eq(shop.getProduct("lamp")?.priceCents, 4000);
  eq(code(shop.addCustomer({ id: "alice", name: "A", email: "a@x", region: "CA" })), "duplicate");
  eq(shop.getCustomer("bob")?.region, "NY");
  eq(code(shop.createOrder({ customerId: "nobody" })), "not_found");
});

Deno.test("stock: add, validate", () => {
  const { shop } = setup();
  eq(shop.stock("pen"), 20);
  eq(must(shop.addStock("pen", 5)), 25);
  eq(code(shop.addStock("ghost", 1)), "not_found");
  eq(code(shop.addStock("pen", 0)), "invalid");
  eq(shop.stock("ghost"), 0);
});

Deno.test("pricing: single taxed item with shipping", () => {
  const { shop } = setup();
  const id = order(shop, "alice", [["pen", 1]]);
  const p = shop.getOrder(id)!.pricing;
  eq(p.subtotalCents, 200);
  eq(p.taxCents, 16);
  eq(p.shippingCents, 650);
  eq(p.totalCents, 866);
});

Deno.test("pricing: untaxed product and mixed order", () => {
  const { shop } = setup();
  eq(shop.getOrder(order(shop, "alice", [["book", 1]]))!.pricing.totalCents, 2150);
  const mixed = shop.getOrder(order(shop, "alice", [["mug", 1], ["book", 1]]))!.pricing;
  eq(mixed.taxCents, 64);
  eq(mixed.shippingCents, 650);
  eq(mixed.totalCents, 3014);
});

Deno.test("pricing: free shipping at threshold, weightless orders ship free", () => {
  const { shop } = setup();
  const big = shop.getOrder(order(shop, "alice", [["lamp", 2]]))!.pricing;
  eq(big.shippingCents, 0);
  eq(big.totalCents, 8640);
  eq(shop.getOrder(order(shop, "alice", [["gem", 1]]))!.pricing.shippingCents, 0);
  const lamp = shop.getOrder(order(shop, "alice", [["lamp", 1]]))!.pricing;
  eq(lamp.shippingCents, 800);
});

Deno.test("pricing: unknown region is untaxed, region comes from customer", () => {
  const { shop } = setup();
  shop.addCustomer({ id: "dan", name: "Dan", email: "d@x", region: "ZZ" });
  eq(shop.getOrder(order(shop, "dan", [["lamp", 1]]))!.pricing.taxCents, 0);
  eq(shop.getOrder(order(shop, "bob", [["lamp", 1]]))!.pricing.taxCents, 160);
  eq(shop.getOrder(order(shop, "carol", [["lamp", 1]]))!.pricing.taxCents, 0);
});

Deno.test("pricing: bulk discount", () => {
  const { shop } = setup();
  const p = shop.getOrder(order(shop, "alice", [["pen", 10]]))!.pricing;
  eq(p.discounts, [{ rule: "bulk", amountCents: 200 }]);
  eq(p.taxCents, 144);
  eq(p.totalCents, 2594);
  const nine = shop.getOrder(order(shop, "alice", [["pen", 9]]))!.pricing;
  eq(nine.discountCents, 0);
});

Deno.test("coupons: percent and fixed", () => {
  const { shop } = setup();
  must(shop.addCoupon({ code: "TEN", kind: "percent", value: 1000 }));
  must(shop.addCoupon({ code: "OFF500", kind: "fixed", value: 500 }));
  const a = order(shop, "alice", [["lamp", 2]]);
  const o = must(shop.applyCoupon(a, "TEN"));
  eq(o.couponCode, "TEN");
  eq(o.pricing.discountCents, 800);
  eq(o.pricing.taxCents, 576);
  eq(o.pricing.totalCents, 7776);
  const b = order(shop, "alice", [["pen", 1]]);
  eq(must(shop.applyCoupon(b, "OFF500")).pricing.discountCents, 200);
  eq(shop.getOrder(b)!.pricing.totalCents, 650);
});

Deno.test("coupons: validation, replacement", () => {
  const { shop, t } = setup();
  must(shop.addCoupon({ code: "BIG", kind: "fixed", value: 100, minSubtotalCents: 1000 }));
  must(shop.addCoupon({ code: "OLD", kind: "percent", value: 500, expiresAt: 2000 }));
  must(shop.addCoupon({ code: "TEN", kind: "percent", value: 1000 }));
  must(shop.addCoupon({ code: "FIVE", kind: "percent", value: 500 }));
  const id = order(shop, "alice", [["pen", 1]]);
  eq(code(shop.applyCoupon(id, "NOPE")), "coupon_invalid");
  eq(code(shop.applyCoupon(id, "BIG")), "coupon_invalid");
  eq(code(shop.addCoupon({ code: "TEN", kind: "percent", value: 1 })), "duplicate");
  eq(code(shop.addCoupon({ code: "X", kind: "percent", value: 20000 })), "invalid");
  must(shop.applyCoupon(id, "OLD"));
  t.now = 2000;
  const id2 = order(shop, "alice", [["pen", 1]]);
  eq(code(shop.applyCoupon(id2, "OLD")), "coupon_expired");
  const id3 = order(shop, "alice", [["lamp", 2]]);
  must(shop.applyCoupon(id3, "TEN"));
  eq(shop.getOrder(id3)!.pricing.discountCents, 800);
  must(shop.applyCoupon(id3, "FIVE"));
  eq(shop.getOrder(id3)!.pricing.discountCents, 400);
});

Deno.test("coupons: max uses are consumed at checkout", () => {
  const { shop } = setup();
  must(shop.addCoupon({ code: "ONCE", kind: "fixed", value: 100, maxUses: 1 }));
  const a = order(shop, "alice", [["pen", 1]]);
  const b = order(shop, "bob", [["pen", 1]]);
  must(shop.applyCoupon(a, "ONCE"));
  must(shop.applyCoupon(b, "ONCE"));
  must(shop.checkout(a));
  eq(code(shop.checkout(b)), "coupon_exhausted");
  eq(shop.getOrder(b)!.status, "open");
  eq(shop.stock("pen"), 19);
  const c = order(shop, "alice", [["pen", 1]]);
  eq(code(shop.applyCoupon(c, "ONCE")), "coupon_exhausted");
});

Deno.test("vip: tiers follow lifetime spend", () => {
  const { shop } = setup();
  eq(shop.tier("carol"), "none");
  makeSilver(shop);
  eq(shop.tier("carol"), "silver");
  eq(shop.getCustomer("carol")!.lifetimeSpendCents, 20000);
  makeGold(shop);
  eq(shop.tier("carol"), "gold");
  eq(shop.tier("ghost"), undefined);
});

Deno.test("vip: silver discount, coupon stacking rules", () => {
  const { shop } = setup();
  makeSilver(shop, "alice");
  const plain = shop.getOrder(order(shop, "alice", [["lamp", 2]]))!.pricing;
  eq(plain.discounts, [{ rule: "vip", amountCents: 400 }]);
  eq(plain.totalCents, 8208);
  must(shop.addCoupon({ code: "TEN", kind: "percent", value: 1000, stackable: true }));
  must(shop.addCoupon({ code: "SOLO", kind: "percent", value: 1000, stackable: false }));
  const a = order(shop, "alice", [["lamp", 2]]);
  const stacked = must(shop.applyCoupon(a, "TEN")).pricing;
  eq(stacked.discounts, [{ rule: "vip", amountCents: 400 }, { rule: "coupon", amountCents: 760 }]);
  eq(stacked.totalCents, 7387);
  const b = order(shop, "alice", [["lamp", 2]]);
  const solo = must(shop.applyCoupon(b, "SOLO")).pricing;
  eq(solo.discounts, [{ rule: "coupon", amountCents: 800 }]);
  eq(solo.totalCents, 7776);
});

Deno.test("vip: gold ships free below the threshold", () => {
  const { shop } = setup();
  makeGold(shop);
  const p = shop.getOrder(order(shop, "carol", [["pen", 1]]))!.pricing;
  eq(p.shippingCents, 0);
  eq(p.discountCents, 20);
});

Deno.test("shipping: threshold applies to the discounted goods value", () => {
  const { shop } = setup();
  must(shop.addCoupon({ code: "OFF1000", kind: "fixed", value: 1000 }));
  must(shop.addCoupon({ code: "OFF500", kind: "fixed", value: 500 }));
  const a = order(shop, "alice", [["lamp", 1], ["book", 1]]);
  eq(shop.getOrder(a)!.pricing.shippingCents, 0);
  const below = must(shop.applyCoupon(a, "OFF1000")).pricing;
  eq(below.shippingCents, 800);
  eq(below.taxCents, 262);
  eq(below.totalCents, 5562);
  const b = order(shop, "alice", [["lamp", 1], ["book", 1]]);
  const exact = must(shop.applyCoupon(b, "OFF500")).pricing;
  eq(exact.shippingCents, 0);
  eq(exact.totalCents, 5291);
});

Deno.test("tax: ship-to region wins over the customer's home region", () => {
  const { shop } = setup();
  const id = order(shop, "bob", [["lamp", 1]], "CA");
  const p = shop.getOrder(id)!.pricing;
  eq(shop.getOrder(id)!.shipRegion, "CA");
  eq(p.taxCents, 320);
  eq(p.totalCents, 5120);
  eq(must(shop.checkout(id)).pricing.totalCents, 5120);
});

Deno.test("checkout: totals, stock, spend, status, audit, email", () => {
  const { shop } = setup();
  const id = order(shop, "alice", [["mug", 2]]);
  const o = must(shop.checkout(id));
  eq(o.status, "paid");
  eq(o.pricing.totalCents, 2378);
  eq(shop.stock("mug"), 18);
  eq(shop.getCustomer("alice")!.lifetimeSpendCents, 2378);
  eq(shop.audit().map((e) => e.action).filter((a) => a === "checkout"), ["checkout"]);
  const m = shop.outbox();
  eq(m.length, 1);
  eq(m[0].to, "alice@example.com");
  eq(m[0].template, "order_confirmation");
  eq(m[0].orderId, id);
  eq(code(shop.checkout(id)), "bad_state");
  eq(code(shop.addItem(id, "pen", 1)), "bad_state");
  eq(shop.stock("mug"), 18);
});

Deno.test("checkout: empty, unknown and out-of-stock orders", () => {
  const { shop } = setup();
  const empty = must(shop.createOrder({ customerId: "alice" })).id;
  eq(code(shop.checkout(empty)), "invalid");
  eq(code(shop.checkout("ord_999")), "not_found");
  const a = order(shop, "alice", [["pen", 15], ["lamp", 1]]);
  const b = order(shop, "bob", [["pen", 10]]);
  must(shop.checkout(a));
  eq(code(shop.checkout(b)), "out_of_stock");
  eq(shop.stock("pen"), 5);
  eq(shop.getOrder(b)!.status, "open");
  eq(shop.outbox().length, 1);
});

Deno.test("checkout: atomic reservation across lines", () => {
  const { shop } = setup();
  const id = order(shop, "alice", [["lamp", 2], ["pen", 21]]);
  eq(code(shop.checkout(id)), "out_of_stock");
  eq(shop.stock("lamp"), 20);
  eq(shop.stock("pen"), 20);
  eq(shop.getCustomer("alice")!.lifetimeSpendCents, 0);
});

Deno.test("checkout: failed attempts are audited", () => {
  const { shop } = setup();
  const id = order(shop, "alice", [["pen", 30]]);
  shop.checkout(id);
  const failed = shop.audit().filter((e) => e.action === "checkout_failed");
  eq(failed.length, 1);
  eq(failed[0].subjectId, id);
});

Deno.test("items merge by sku and keep quantities", () => {
  const { shop } = setup();
  const id = order(shop, "alice", [["pen", 2], ["pen", 3]]);
  eq(shop.getOrder(id)!.items, [{ sku: "pen", qty: 5, unitPriceCents: 200 }]);
  eq(code(shop.addItem(id, "pen", 0)), "invalid");
  eq(code(shop.addItem(id, "ghost", 1)), "not_found");
  eq(code(shop.addItem("ord_404", "pen", 1)), "not_found");
});

Deno.test("refund: full refund returns the whole total and restores stock", () => {
  const { shop } = setup();
  const id = order(shop, "alice", [["mug", 2]]);
  must(shop.checkout(id));
  const r = must(shop.refund(id));
  eq(r.amountCents, 2378);
  eq(r.status, "refunded");
  eq(shop.stock("mug"), 20);
  eq(shop.getCustomer("alice")!.lifetimeSpendCents, 0);
  eq(shop.getOrder(id)!.refundedCents, 2378);
  eq(code(shop.refund(id)), "bad_state");
});

Deno.test("refund: partial refunds restore stock, split amounts and add up", () => {
  const { shop } = setup();
  const id = order(shop, "alice", [["mug", 2]]);
  must(shop.checkout(id));
  const first = must(shop.refund(id, [{ sku: "mug", qty: 1 }]));
  eq(first.amountCents, 864);
  eq(first.status, "partially_refunded");
  eq(shop.stock("mug"), 19);
  eq(shop.getCustomer("alice")!.lifetimeSpendCents, 2378 - 864);
  const second = must(shop.refund(id, [{ sku: "mug", qty: 1 }]));
  eq(second.amountCents, 864 + 650);
  eq(second.status, "refunded");
  eq(shop.stock("mug"), 20);
  eq(shop.getOrder(id)!.refundedCents, 2378);
});

Deno.test("refund: validation", () => {
  const { shop } = setup();
  const open = order(shop, "alice", [["pen", 1]]);
  eq(code(shop.refund(open)), "bad_state");
  eq(code(shop.refund("ord_404")), "not_found");
  const id = order(shop, "alice", [["pen", 2], ["mug", 1]]);
  must(shop.checkout(id));
  eq(code(shop.refund(id, [{ sku: "pen", qty: 3 }])), "invalid");
  eq(code(shop.refund(id, [{ sku: "lamp", qty: 1 }])), "invalid");
  eq(code(shop.refund(id, [{ sku: "pen", qty: 0 }])), "invalid");
  eq(shop.stock("pen"), 18);
});

Deno.test("refund: proportional split across different lines", () => {
  const { shop } = setup();
  const id = order(shop, "alice", [["pen", 1], ["lamp", 1]]);
  const o = must(shop.checkout(id));
  eq(o.pricing.totalCents, 4200 + 336 + 800);
  eq(o.lineNetCents.pen + o.lineNetCents.lamp, 4200 + 336);
  const a = must(shop.refund(id, [{ sku: "pen", qty: 1 }]));
  eq(a.amountCents, 216);
  const b = must(shop.refund(id, [{ sku: "lamp", qty: 1 }]));
  eq(b.amountCents, 4320 + 800);
});

Deno.test("refund: audit entries and emails", () => {
  const { shop } = setup();
  const id = order(shop, "alice", [["mug", 2]]);
  must(shop.checkout(id));
  must(shop.refund(id, [{ sku: "mug", qty: 1 }]));
  must(shop.refund(id));
  const refunds = shop.audit().filter((e) => e.action === "refund");
  eq(refunds.map((e) => e.detail), ["864", "1514"]);
  eq(shop.outbox().map((m) => m.template), ["order_confirmation", "refund_issued", "refund_issued"]);
});

Deno.test("refund: spend drop can demote a VIP", () => {
  const { shop } = setup();
  const id = order(shop, "carol", [["gem", 1]]);
  must(shop.checkout(id));
  eq(shop.tier("carol"), "silver");
  must(shop.refund(id));
  eq(shop.tier("carol"), "none");
});

Deno.test("audit: lifecycle entries in order", () => {
  const { shop, t } = setup();
  t.now = 5000;
  const id = order(shop, "alice", [["pen", 1]]);
  must(shop.addCoupon({ code: "OFF", kind: "fixed", value: 50 }));
  must(shop.applyCoupon(id, "OFF"));
  must(shop.checkout(id));
  const mine = shop.audit().filter((e) => e.subjectId === id).map((e) => e.action);
  eq(mine, ["order_created", "coupon_applied", "checkout"]);
  eq(shop.audit().filter((e) => e.action === "stock_added").length, 6);
  eq(shop.audit().at(-1)!.at, 5000);
});

Deno.test("independence: two shops share nothing", () => {
  const a = setup().shop;
  const b = createShop();
  eq(b.stock("pen"), 0);
  eq(b.audit().length, 0);
  eq(a.audit().length > 0, true);
  eq(b.getCustomer("alice"), undefined);
});

Deno.test("custom config and rules are honored", () => {
  const { shop } = setup({ config: { freeShippingThresholdCents: 100 } });
  eq(shop.getOrder(order(shop, "alice", [["pen", 1]]))!.pricing.shippingCents, 0);
  const none = setup({ rules: [] }).shop;
  must(none.addCoupon({ code: "TEN", kind: "percent", value: 1000 }));
  const id = order(none, "alice", [["lamp", 2]]);
  eq(must(none.applyCoupon(id, "TEN")).pricing.discountCents, 0);
});
