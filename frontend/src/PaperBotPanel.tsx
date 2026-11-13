import { useState } from "react";
import { MarketValue } from "./components/MarketValue";
import { Alert } from "./components/ui/Alert";
import { Button } from "./components/ui/Button";
import { Input } from "./components/ui/Input";
import { Label } from "./components/ui/Label";
import { Select } from "./components/ui/Select";
import { manualOrderText as t } from "./manualOrderMessages";
import { paperBotText as bt } from "./paperBotMessages";

/** Uses TailAdmin form controls; display-only draft, never an order or bot command. */
export function PaperBotPanel({ available, loading }: {
  available: string | null;
  loading: boolean;
}) {
  const [budget, setBudget] = useState("");
  const balance = available !== null
    ? <MarketValue amount={available} unit="USDT" grouped/>
    : loading ? bt("loading") : t("unavailable");

  return <section aria-labelledby="paper-bot-title" className="space-y-4">
    <h2 id="paper-bot-title" className="border-b border-gray-200 pb-3 text-sm font-semibold dark:border-gray-800">
      {bt("title")}
    </h2>
    <div>
      <Label htmlFor="paper-bot-strategy">{bt("strategy")}</Label>
      <Select id="paper-bot-strategy" defaultValue="grid-close-system">
        <option value="grid-close-system">Grid Close System</option>
      </Select>
    </div>
    <div>
      <dl className="flex flex-wrap items-baseline justify-between gap-x-2 gap-y-1 text-sm" aria-live="polite">
        <dt className="text-gray-500 dark:text-gray-400">{t("available")}</dt>
        <dd className="font-medium tabular-nums">{balance}</dd>
      </dl>
      <p role="status" className="sr-only">{loading && available !== null ? bt("updating") : ""}</p>
    </div>
    <div>
      <Label htmlFor="paper-bot-budget">{bt("budget")}</Label>
      <Input id="paper-bot-budget" type="text" inputMode="decimal" autoComplete="off" maxLength={256}
        value={budget} onChange={event => setBudget(event.target.value)} aria-describedby="paper-bot-notice"/>
    </div>
    <Button type="button" disabled className="w-full" aria-describedby="paper-bot-notice">
      {bt("start")}
    </Button>
    <div id="paper-bot-notice">
      <Alert variant="info" title={bt("unavailable")} message={bt("notice")}/>
    </div>
  </section>;
}
