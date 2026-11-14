import { fireEvent, screen } from "@testing-library/react";
import { killSwitchText as t } from "../src/killSwitchMessages";

/** Exercise the real settings trigger before details/same-key retry assertions. */
export function openStopSettings() {
  const trigger = screen.getByRole("button", { name: t("settings") });
  if (trigger.getAttribute("aria-expanded") !== "true") fireEvent.click(trigger);
  return trigger;
}
