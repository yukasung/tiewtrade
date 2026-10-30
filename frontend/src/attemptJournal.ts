/** Shared durable request identity storage. Only validated, non-secret intent data belongs here. */
export class JournalUnavailable extends Error {}
export type AttemptJournal<T> = {
  read: (scope: string) => T | null;
  write: (value: T) => void;
  clear: (scope: string, expectedKey?: string) => void;
};
export function sessionJournal<T extends { key: string }>(
  prefix: string,
  scopeOf: (value: T) => string,
  valid: (value: unknown, scope: string) => value is T,
): AttemptJournal<T> {
  const read = (scope: string): T | null => {
    try {
      const raw = window.sessionStorage.getItem(prefix + scope);
      if (raw === null) return null;
      const value: unknown = JSON.parse(raw);
      if (!valid(value, scope)) throw new JournalUnavailable();
      return value;
    } catch { throw new JournalUnavailable(); }
  };
  return {
    read,
    write: value => {
      try {
        const scope = scopeOf(value);
        if (!valid(value, scope)) throw new JournalUnavailable();
        const encoded = JSON.stringify(value);
        window.sessionStorage.setItem(prefix + scope, encoded);
        if (window.sessionStorage.getItem(prefix + scope) !== encoded) throw new JournalUnavailable();
      } catch { throw new JournalUnavailable(); }
    },
    clear: (scope, expectedKey) => {
      try {
        if (expectedKey !== undefined && read(scope)?.key !== expectedKey) return;
        window.sessionStorage.removeItem(prefix + scope);
        if (window.sessionStorage.getItem(prefix + scope) !== null) throw new JournalUnavailable();
      } catch { throw new JournalUnavailable(); }
    },
  };
}
