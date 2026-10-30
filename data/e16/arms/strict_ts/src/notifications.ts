import type { Ctx, Customer, Db, EmailMessage, EmailTemplate } from "./types.ts";

export function subjectFor(template: EmailTemplate, orderId: string): string {
  switch (template) {
    case "order_confirmation":
      return `Your order ${orderId} is confirmed`;
    case "refund_issued":
      return `A refund for order ${orderId} was issued`;
  }
}

/** Appends a message to `ctx.db.outbox`. */
export function queueEmail(
  ctx: Ctx,
  customer: Customer,
  template: EmailTemplate,
  orderId: string,
): void {
  ctx.db.outbox.push({
    to: customer.email,
    subject: subjectFor(template, orderId),
    template,
    orderId,
    at: ctx.clock.now(),
  });
}

export function listOutbox(db: Db): EmailMessage[] {
  return db.outbox.map((m) => ({ ...m }));
}
