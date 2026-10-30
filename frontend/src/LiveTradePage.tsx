import { RiskLimitPanel } from "./RiskLimitPanel";
import { ManualOrderForm } from "./ManualOrderForm";
import { Badge } from "./components/ui/Badge";
import { ComponentCard } from "./components/ui/ComponentCard";
import { manualOrderText as t } from "./manualOrderMessages";
export function LiveTradePage({ owner }: { owner: string }) {
  return <div className="space-y-6"><p className="text-2xl font-semibold"><Badge color="warning">{t("live")}</Badge></p>
    <RiskLimitPanel owner={owner} mode="LIVE"/>
    <p role="status">{t("liveUnavailable")}</p>
    <ComponentCard title={t("form")} headingId="live-manual-form-heading"><ManualOrderForm mode="LIVE" bases={[]} base="" onBase={() => {}} scope={null} disabled canSubmit={() => false} onSubmit={() => {}}/></ComponentCard>
  </div>;
}
