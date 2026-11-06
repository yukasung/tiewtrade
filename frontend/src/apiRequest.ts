import { ApiRequestError } from "./auth";

export type ApiErrorPolicy = Readonly<{
  allowedCodes: readonly string[];
  fallbackCode: string;
  statusFallbacks?: ReadonlyMap<number, string>;
  preserveAbort: boolean;
  preserveRetryAfter: boolean;
}>;

/** Sanitize rejected requests without changing each feature's error/recovery policy. */
export function createSafeRequest(policy: ApiErrorPolicy): <T>(request: Promise<T>) => Promise<T> {
  return async <T>(request: Promise<T>): Promise<T> => {
    try {
      return await request;
    } catch (cause: unknown) {
      if (policy.preserveAbort && cause instanceof DOMException && cause.name === "AbortError") {
        throw cause;
      }
      const error = cause instanceof ApiRequestError ? cause : null;
      let code = policy.fallbackCode;
      if (error !== null) {
        code = policy.allowedCodes.includes(error.message)
          ? error.message
          : policy.statusFallbacks?.get(error.status) ?? policy.fallbackCode;
      }
      // Never attach raw errors or payloads to errors retained by callers/query caches.
      throw new ApiRequestError(
        code,
        error?.status ?? 0,
        policy.preserveRetryAfter ? error?.retryAt ?? null : null,
      );
    }
  };
}
