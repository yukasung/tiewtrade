import type { components } from "./api-types";
import { ApiRequestError, send } from "./auth";

export type KeyView = components["schemas"]["KeyView"];
export type AddKeyRequest = components["schemas"]["AddKeyRequest"];
type AddedKey = components["schemas"]["AddedKey"];
type RetryAccepted = components["schemas"]["RetryAccepted"];

/** อย่าเก็บ error ดิบใน mutation cache แม้ server/proxy ตอบค่าที่ไม่คาดไว้ */
async function safe<T>(request: Promise<T>): Promise<T> {
  try {
    return await request;
  } catch (cause: unknown) {
    const error = new ApiRequestError(
      "API_KEY_REQUEST_FAILED",
      cause instanceof ApiRequestError ? cause.status : 0,
    );
    if (cause instanceof ApiRequestError && cause.retryAt !== null) {
      throw new ApiRequestError(error.message, cause.status, cause.retryAt);
    }
    throw error;
  }
}

export function fetchApiKeys(signal?: AbortSignal): Promise<KeyView[]> {
  return safe(
    send<KeyView[]>("/api-keys", undefined, undefined, "GET", signal),
  );
}
export function addApiKey(
  input: AddKeyRequest,
  code: string,
): Promise<AddedKey> {
  return safe(send<AddedKey>("/api-keys", input, code));
}
export function retryApiKey(id: string): Promise<RetryAccepted> {
  return safe(
    send<RetryAccepted>(`/api-keys/${encodeURIComponent(id)}/retry`, {}),
  );
}
export function deleteApiKey(id: string): Promise<void> {
  return safe(
    send<void>(
      `/api-keys/${encodeURIComponent(id)}`,
      undefined,
      undefined,
      "DELETE",
    ),
  );
}
