import type { Cents, Ctx, Order, OrderStatus, Result } from "./types.ts";
import { err, ok } from "./types.ts";
import { getCustomer, adjustSpend } from "./customers.ts";
import { release, type StockLine } from "./inventory.ts";
import { record } from "./audit.ts";
import { queueEmail } from "./notifications.ts";
import { getOrder } from "./orders.ts";

export interface RefundResult {
  orderId: string;
  amountCents: Cents;
  status: OrderStatus;
}

/** Units of each line not yet refunded. */
export function remainingLines(order: Order): StockLine[] {
  return order.items
    .map((i) => ({ sku: i.sku, qty: i.qty - (order.refundedByLine[i.sku]?.qty ?? 0) }))
    .filter((l) => l.qty > 0);
}

function mergeLines(lines: readonly StockLine[]): StockLine[] {
  const byLine = new Map<string, number>();
  for (const l of lines) byLine.set(l.sku, (byLine.get(l.sku) ?? 0) + l.qty);
  return [...byLine.entries()].map(([sku, qty]) => ({ sku, qty }));
}

/**
 * Refunds `requested` units (default: everything left). Restores stock, reduces the
 * customer's lifetime spend, audits and emails. The shipping charge is refunded only
 * when the last unit goes back.
 */
export function refund(ctx: Ctx, orderId: string, requested?: readonly StockLine[]): Result<RefundResult> {
  const order = getOrder(ctx.db, orderId);
  if (!order) return err("not_found", `unknown order ${orderId}`);
  if (order.status !== "paid" && order.status !== "partially_refunded") {
    return err("bad_state", `order ${orderId} is ${order.status}`);
  }
  const lines = mergeLines(requested ?? remainingLines(order));
  if (lines.length === 0) return err("invalid", "nothing to refund");

  const refundedByLine = { ...order.refundedByLine };
  let amount = 0;
  for (const line of lines) {
    const item = order.items.find((i) => i.sku === line.sku);
    if (!item) return err("invalid", `sku ${line.sku} is not in the order`);
    if (!Number.isInteger(line.qty) || line.qty <= 0) return err("invalid", "qty must be a positive integer");
    const prior = refundedByLine[line.sku] ?? { qty: 0, cents: 0 };
    if (prior.qty + line.qty > item.qty) return err("invalid", `cannot refund more ${line.sku} than ordered`);
    const net = order.lineNetCents[line.sku] ?? 0;
    const cents = prior.qty + line.qty === item.qty
      ? net - prior.cents
      : Math.round((net * line.qty) / item.qty);
    refundedByLine[line.sku] = { qty: prior.qty + line.qty, cents: prior.cents + cents };
    amount += cents;
  }

  const complete = order.items.every((i) => (refundedByLine[i.sku]?.qty ?? 0) === i.qty);
  if (complete) amount += order.pricing.shippingCents;

  const status: OrderStatus = complete ? "refunded" : "partially_refunded";
  const updated: Order = { ...order, status, refundedByLine, refundedCents: order.refundedCents + amount };
  ctx.db.orders.set(orderId, updated);
  release(ctx.db, lines);
  adjustSpend(ctx.db, order.customerId, -amount);
  record(ctx.log, ctx.clock, "refund", orderId, String(amount));
  const customer = getCustomer(ctx.db, order.customerId);
  if (customer) queueEmail(ctx, customer, "refund_issued", orderId);
  return ok({ orderId, amountCents: amount, status });
}
