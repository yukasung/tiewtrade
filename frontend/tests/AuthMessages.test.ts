import { expect, it } from "vitest";
import { authText } from "../src/authMessages";

it("translates auth/TOTP/health copy and interpolates recovery counts in both languages", () => {
  expect(authText("login", { lng: "th" })).toBe("เข้าสู่ระบบ");
  expect(authText("login", { lng: "en" })).toBe("Sign in");
  expect(authText("codesLeft", { lng: "th", count: 3 })).toContain("3");
  expect(authText("codesLeft", { lng: "en", count: 3 })).toContain("3");
  expect(authText("totpHeading", { lng: "en" })).toBe(
    "Two-factor authentication",
  );
  expect(authText("serverTime", { lng: "en" })).toBe("Server time");
});
