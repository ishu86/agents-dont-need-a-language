import { createShop } from "../src/index.ts";

function eq<T>(actual: T, expected: T, msg = "") {
  if (JSON.stringify(actual) !== JSON.stringify(expected)) {
    throw new Error(`${msg} expected ${JSON.stringify(expected)}, got ${JSON.stringify(actual)}`);
  }
}

function setup() {
  const shop = createShop({ now: () => 1000 });
  shop.addProduct({ sku: "mug", name: "Mug", priceCents: 800, weightG: 300 });
  shop.addProduct({ sku: "lamp", name: "Lamp", priceCents: 4000, weightG: 1500 });
  shop.addStock("mug", 10);
  shop.addStock("lamp", 3);
  shop.addCustomer({ id: "alice", name: "Alice", email: "alice@example.com", region: "CA" });
  return shop;
}

function newOrder(shop: ReturnType<typeof setup>) {
  const r = shop.createOrder({ customerId: "alice" });
  if (!r.ok) throw new Error(r.error.message);
  return r.value.id;
}

Deno.test("checkout totals include tax and shipping", () => {
  const shop = setup();
  const id = newOrder(shop);
  shop.addItem(id, "mug", 1);
  const r = shop.checkout(id);
  if (!r.ok) throw new Error(r.error.message);
  // 800 + 8% tax (64) + shipping 500 + 150 per started kg
  eq(r.value.pricing.totalCents, 800 + 64 + 650);
  eq(shop.stock("mug"), 9);
});

Deno.test("checkout fails when stock is short", () => {
  const shop = setup();
  const id = newOrder(shop);
  shop.addItem(id, "lamp", 4);
  const r = shop.checkout(id);
  eq(r.ok, false);
  if (!r.ok) eq(r.error.code, "out_of_stock");
  eq(shop.stock("lamp"), 3);
});

Deno.test("percent coupon discounts the subtotal", () => {
  const shop = setup();
  shop.addCoupon({ code: "TEN", kind: "percent", value: 1000 });
  const id = newOrder(shop);
  shop.addItem(id, "lamp", 2);
  const r = shop.applyCoupon(id, "TEN");
  if (!r.ok) throw new Error(r.error.message);
  eq(r.value.pricing.discountCents, 800);
});

Deno.test("full refund restores stock", () => {
  const shop = setup();
  const id = newOrder(shop);
  shop.addItem(id, "mug", 2);
  shop.checkout(id);
  eq(shop.stock("mug"), 8);
  const r = shop.refund(id);
  eq(r.ok, true);
  eq(shop.stock("mug"), 10);
  eq(shop.getOrder(id)?.status, "refunded");
});

Deno.test("checkout queues a confirmation email", () => {
  const shop = setup();
  const id = newOrder(shop);
  shop.addItem(id, "mug", 1);
  shop.checkout(id);
  eq(shop.outbox().map((m) => m.template), ["order_confirmation"]);
});

Deno.test("unknown sku is rejected", () => {
  const shop = setup();
  const id = newOrder(shop);
  const r = shop.addItem(id, "nope", 1);
  eq(r.ok, false);
});
