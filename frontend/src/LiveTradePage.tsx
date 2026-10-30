import { useEffect, useMemo, useState } from "react";
import { CandlestickChartPanel } from "./CandlestickChartPanel";
import { RiskLimitPanel } from "./RiskLimitPanel";
import { ManualOrderForm } from "./ManualOrderForm";
import { Button } from "./components/ui/Button";
import { TradingWorkspace } from "./TradingWorkspace";
import { activeBases, useMarketCatalog } from "./marketCatalog";
import { manualOrderText as t } from "./manualOrderMessages";
import { useTradingPair } from "./useTradingPair";
export function LiveTradePage({ owner }: { owner: string }) {
  const catalog = useMarketCatalog();
  const bases = useMemo(() => activeBases(catalog.data), [catalog.data]);
  const { base, changeBase, market, setMarketSnapshot } = useTradingPair();
  const [showDetails, setShowDetails] = useState(false);
  useEffect(() => {
    if (bases.length > 0 && !bases.includes(base)) changeBase(bases[0]!);
  }, [base, bases, changeBase]);
  const form = <section aria-labelledby="live-manual-form-heading" className="space-y-5">
    <div><h2 id="live-manual-form-heading" className="text-lg font-semibold">{t("form")}</h2>
      <p role="status" className="text-sm text-gray-500 dark:text-gray-400">{t("liveUnavailable")}</p></div>
    <ManualOrderForm key={base} mode="LIVE" bases={bases} base={base} onBase={changeBase} showPairSelector={false}
      scope={null} disabled canSubmit={() => false} onSubmit={() => {}}/>
  </section>;
  const details = <div className="trade-workspace-details space-y-4">
    <Button variant="outline" onClick={() => setShowDetails(value => !value)} aria-expanded={showDetails}>
      {t(showDetails ? "hideDetails" : "riskDetails")}
    </Button>
    {showDetails && <RiskLimitPanel owner={owner} mode="LIVE"/>}
  </div>;
  return <TradingWorkspace mode="LIVE" bases={bases} base={base} onBase={changeBase}
    pairDisabled={catalog.isPending || catalog.isError}
    marketPrice={market?.price} marketObservedAt={market?.observedAt}
    marketStatus={market ? t("marketReady") : t("marketLoading")}
    chart={<CandlestickChartPanel userId={owner} base={base} onBaseChange={changeBase} embedded onMarketSnapshot={setMarketSnapshot}/>} form={form} details={details}/>;
}
