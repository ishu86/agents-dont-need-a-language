import { state } from "./state.ts";

const subjects: any = {
  order_confirmation: (orderId: string) => `Your order ${orderId} is confirmed`,
  refund_issued: (orderId: string) => `A refund for order ${orderId} was issued`,
};

export function subjectFor(template: string, orderId: string): string {
  return subjects[template](orderId);
}

export function queueEmail(customer: any, template: string, orderId: string): void {
  state.outbox.push({
    to: customer.email,
    subject: subjectFor(template, orderId),
    template,
    orderId,
    at: state.clock.now(),
  });
}

export function listOutbox(): any[] {
  return state.outbox.map((m: any) => ({ ...m }));
}

export function outboxFor(email: string): any[] {
  return listOutbox().filter((m: any) => m.to === email);
}

export function countByTemplate(): any {
  const counts: any = {};
  for (const m of state.outbox) counts[m.template] = (counts[m.template] || 0) + 1;
  return counts;
}
