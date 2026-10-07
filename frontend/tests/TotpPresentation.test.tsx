import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { TotpPanel } from "../src/TotpPanel";

const api = vi.hoisted(() => ({
  startTotpSetup: vi.fn(),
  startTotpReplacement: vi.fn(),
  confirmTotpSetup: vi.fn(),
  reissueRecoveryCodes: vi.fn(),
  disableTotp: vi.fn(),
}));
vi.mock("../src/auth", () => api);
vi.mock("qrcode", () => ({
  default: {
    toDataURL: vi.fn().mockResolvedValue("data:image/png;base64,test"),
  },
}));
afterEach(() => {
  cleanup();
  vi.resetAllMocks();
});

function renderEnabled() {
  const onChanged = vi.fn().mockResolvedValue(undefined);
  render(
    <TotpPanel
      identity={{
        user_id: "00000000-0000-4000-8000-000000000001",
        totp_enabled: true,
      }}
      onChanged={onChanged}
    />,
  );
  fireEvent.change(screen.getByLabelText<HTMLInputElement>("รหัสผ่านปัจจุบัน"), {
    target: { value: "test-password-only" },
  });
  fireEvent.change(screen.getByLabelText<HTMLInputElement>("รหัสจากแอปปัจจุบัน"), {
    target: { value: "123456" },
  });
  return onChanged;
}
it("uses the existing replacement API and shows its URI in the themed enrollment section", async () => {
  api.startTotpReplacement.mockResolvedValue({
    otpauth_uri: "otpauth://totp/test?secret=FAKE",
  });
  renderEnabled();
  fireEvent.click(screen.getByTestId<HTMLButtonElement>("replace-totp"));
  await waitFor(() =>
    expect(screen.getByTestId("otpauth-uri").textContent).toContain(
      "secret=FAKE",
    ),
  );
  expect(api.startTotpReplacement).toHaveBeenCalledWith(
    "test-password-only",
    "123456",
  );
  expect((screen.getByLabelText<HTMLInputElement>("รหัสจากแอป")).value).toBe(
    "",
  );
  expect(screen.getByTestId<HTMLButtonElement>("confirm-totp").className).toContain(
    "account-button",
  );
});
it("shows reissued recovery codes and clears the existing credential fields", async () => {
  api.reissueRecoveryCodes.mockResolvedValue({
    recovery_codes: ["TEST-CODE-ONE", "TEST-CODE-TWO"],
  });
  renderEnabled();
  fireEvent.click(screen.getByTestId<HTMLButtonElement>("reissue-codes"));
  await waitFor(() =>
    expect(screen.getByTestId("recovery-codes").textContent).toContain(
      "TEST-CODE-ONE",
    ),
  );
  expect(api.reissueRecoveryCodes).toHaveBeenCalledWith(
    "test-password-only",
    "123456",
  );
  expect(
    (screen.getByLabelText<HTMLInputElement>("รหัสผ่านปัจจุบัน")).value,
  ).toBe("");
  expect(
    (screen.getByLabelText<HTMLInputElement>("รหัสจากแอปปัจจุบัน")).value,
  ).toBe("");
});
it("disables TOTP through the existing callback and clears credential fields", async () => {
  api.disableTotp.mockResolvedValue(undefined);
  const onChanged = renderEnabled();
  fireEvent.click(screen.getByTestId<HTMLButtonElement>("disable-totp"));
  await waitFor(() => expect(onChanged).toHaveBeenCalledOnce());
  expect(api.disableTotp).toHaveBeenCalledWith("test-password-only", "123456");
  expect(
    (screen.getByLabelText<HTMLInputElement>("รหัสผ่านปัจจุบัน")).value,
  ).toBe("");
  expect(
    (screen.getByLabelText<HTMLInputElement>("รหัสจากแอปปัจจุบัน")).value,
  ).toBe("");
});
it("keeps all TOTP actions disabled while waiting and exposes a failure as an alert", async () => {
  let rejectRequest!: (error: Error) => void;
  api.startTotpReplacement.mockReturnValue(
    new Promise((_, reject) => {
      rejectRequest = reject;
    }),
  );
  const onChanged = renderEnabled();
  fireEvent.click(screen.getByTestId<HTMLButtonElement>("replace-totp"));
  for (const id of ["replace-totp", "reissue-codes", "disable-totp"])
    expect((screen.getByTestId<HTMLButtonElement>(id)).disabled).toBe(true);
  rejectRequest(new Error("test refusal"));
  await waitFor(() =>
    expect(screen.getByRole("alert").textContent).toBe("test refusal"),
  );
  expect(
    (screen.getByTestId<HTMLButtonElement>("replace-totp")).disabled,
  ).toBe(false);
  expect(onChanged).not.toHaveBeenCalled();
});
