import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, expect, it } from "vitest";
import { AuthLayout } from "../src/layout/AuthLayout";

afterEach(cleanup);
it("renders an auth form with TiewTrade branding and no account navigation or nested main", () => {
  render(
    <main>
      <AuthLayout>
        <form aria-label="sign in" />
      </AuthLayout>
    </main>,
  );
  expect(
    screen.getByRole("form", { name: "sign in" }).closest(".auth-layout"),
  ).not.toBeNull();
  expect(screen.getAllByText("TiewTrade").length).toBeGreaterThan(0);
  expect(screen.queryByRole("navigation")).toBeNull();
  expect(screen.getAllByRole("main")).toHaveLength(1);
});
