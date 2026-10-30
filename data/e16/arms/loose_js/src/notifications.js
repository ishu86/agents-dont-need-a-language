import { state } from "./state.js";

const subjects = {
  order_confirmation: (orderId) => `Your order ${orderId} is confirmed`,
  refund_issued: (orderId) => `A refund for order ${orderId} was issued`,
};

export function subjectFor(template, orderId) {
  return subjects[template](orderId);
}

export function queueEmail(customer, template, orderId) {
  state.outbox.push({
    to: customer.email,
    subject: subjectFor(template, orderId),
    template,
    orderId,
    at: state.clock.now(),
  });
}

export function listOutbox() {
  return state.outbox.map((m) => ({ ...m }));
}

export function outboxFor(email) {
  return listOutbox().filter((m) => m.to === email);
}

export function countByTemplate() {
  const counts = {};
  for (const m of state.outbox) counts[m.template] = (counts[m.template] || 0) + 1;
  return counts;
}
