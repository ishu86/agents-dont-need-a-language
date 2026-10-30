import { getCustomer, adjustSpend } from "./customers.ts";
import { release } from "./inventory.ts";
import { record } from "./audit.ts";
import { queueEmail } from "./notifications.ts";
import { Order, getOrder } from "./orders.ts";

// Units of each line not yet refunded.
(Order.prototype as any).remainingLines = function (this: any) {
  return this.items
    .map((i: any) => ({ sku: i.sku, qty: i.qty - (this.refundedByLine[i.sku] ? this.refundedByLine[i.sku].qty : 0) }))
    .filter((l: any) => l.qty > 0);
};

function mergeLines(lines: any[]): any[] {
  const byLine = new Map<string, number>();
  for (const l of lines) byLine.set(l.sku, (byLine.get(l.sku) || 0) + l.qty);
  return [...byLine.entries()].map(([sku, qty]) => ({ sku, qty }));
}

// Refunds `requested` units (default: everything left). Restores stock, reduces the
// customer's lifetime spend, audits and emails. The shipping charge is refunded only
// when the last unit goes back.
export function refund(orderId: string, requested?: any[]): any {
  const order = getOrder(orderId);
  if (!order) throw `not_found: unknown order ${orderId}`;
  if (order.status !== "paid" && order.status !== "partially_refunded") {
    throw `bad_state: order ${orderId} is ${order.status}`;
  }
  const lines = mergeLines(requested || order.remainingLines());
  if (lines.length === 0) throw "invalid: nothing to refund";

  const refundedByLine: any = { ...order.refundedByLine };
  let amount = 0;
  for (const line of lines) {
    const item = order.items.find((i: any) => i.sku === line.sku);
    if (!item) throw `invalid: sku ${line.sku} is not in the order`;
    if (!Number.isInteger(line.qty) || line.qty <= 0) throw "invalid: qty must be a positive integer";
    const prior = refundedByLine[line.sku] || { qty: 0, cents: 0 };
    if (prior.qty + line.qty > item.qty) throw `invalid: cannot refund more ${line.sku} than ordered`;
    const net = order.lineNetCents[line.sku] || 0;
    const cents = prior.qty + line.qty === item.qty
      ? net - prior.cents
      : Math.round((net * line.qty) / item.qty);
    refundedByLine[line.sku] = { qty: prior.qty + line.qty, cents: prior.cents + cents };
    amount += cents;
  }

  const complete = order.items.every((i: any) => (refundedByLine[i.sku] ? refundedByLine[i.sku].qty : 0) === i.qty);
  if (complete) amount += order.pricing.shippingCents;

  order.status = complete ? "refunded" : "partially_refunded";
  order.refundedByLine = refundedByLine;
  order.refundedCents += amount;
  release(lines);
  adjustSpend(order.customerId, -amount);
  record("refund", orderId, String(amount));
  const customer = getCustomer(order.customerId);
  if (customer) queueEmail(customer, "refund_issued", orderId);
  return { orderId, amountCents: amount, status: order.status };
}

// Cents still refundable on an order, shipping excluded.
export function refundableCents(order: any): number {
  let left = 0;
  for (const sku of Object.keys(order.lineNetCents)) {
    const done = order.refundedByLine[sku];
    left += order.lineNetCents[sku] - (done ? done.cents : 0);
  }
  return left;
}
