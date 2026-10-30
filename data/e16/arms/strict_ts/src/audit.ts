import type { AuditEntry, AuditLog, Clock } from "./types.ts";

/** Appends one entry to `log`. */
export function record(
  log: AuditLog,
  clock: Clock,
  action: string,
  subjectId: string,
  detail = "",
): void {
  log.entries.push({ at: clock.now(), action, subjectId, detail });
}

export function entries(log: AuditLog): AuditEntry[] {
  return log.entries.map((e) => ({ ...e }));
}

export function entriesFor(log: AuditLog, subjectId: string): AuditEntry[] {
  return entries(log).filter((e) => e.subjectId === subjectId);
}
