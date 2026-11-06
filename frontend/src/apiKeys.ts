import type { components } from "./api-types";
import { send } from "./auth";
import { createSafeRequest } from "./apiRequest";

export type KeyView = components["schemas"]["KeyView"];
export type AddKeyRequest = components["schemas"]["AddKeyRequest"];
type AddedKey = components["schemas"]["AddedKey"];
type RetryAccepted = components["schemas"]["RetryAccepted"];

/** อย่าเก็บ error ดิบใน mutation cache แม้ server/proxy ตอบค่าที่ไม่คาดไว้ */
const safe = createSafeRequest({
  allowedCodes: [],
  fallbackCode: "API_KEY_REQUEST_FAILED",
  preserveAbort: false,
  preserveRetryAfter: true,
});

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
