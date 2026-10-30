import { state } from "./state.js";

export function record(action, subjectId, detail) {
  state.auditLog.push({ at: state.clock.now(), action, subjectId, detail: detail || "" });
}

export function entries() {
  return state.auditLog.map((e) => ({ ...e }));
}

export function entriesFor(subjectId) {
  return entries().filter((e) => e.subjectId === subjectId);
}

export function countByAction() {
  const counts = {};
  for (const e of state.auditLog) counts[e.action] = (counts[e.action] || 0) + 1;
  return counts;
}

// Entries recorded in the half-open window [from, to).
export function entriesBetween(from, to) {
  return entries().filter((e) => e.at >= from && e.at < to);
}
