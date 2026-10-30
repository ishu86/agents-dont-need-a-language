import { state } from "./state.ts";

export function record(action: string, subjectId: string, detail?: any): void {
  state.auditLog.push({ at: state.clock.now(), action, subjectId, detail: detail || "" });
}

export function entries(): any[] {
  return state.auditLog.map((e) => ({ ...e }));
}

export function entriesFor(subjectId: string): any[] {
  return entries().filter((e) => e.subjectId === subjectId);
}

export function countByAction(): any {
  const counts: any = {};
  for (const e of state.auditLog) counts[e.action] = (counts[e.action] || 0) + 1;
  return counts;
}

// Entries recorded in the half-open window [from, to).
export function entriesBetween(from: number, to: number): any[] {
  return entries().filter((e) => e.at >= from && e.at < to);
}
