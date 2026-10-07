import ComponentCard from "../../common/ComponentCard";
import DefaultTooltip from "./DefaultTooltip";
import WhiteAndDarkTooltip from "./WhiteAndDarkTooltip";
import TooltipPlacement from "./TooltipPlacement";
import LightNoBorderTooltip from "./LightNoBorderTooltip";
import DarkNoBorderTooltip from "./DarkNoBorderTooltip";

export default function TooltipExample() {
  return (
    <div className="space-y-5 sm:space-y-6">
      <ComponentCard title="Default Tooltip">
        <DefaultTooltip />
      </ComponentCard>
      <ComponentCard title="White and Dark Tooltip">
        <WhiteAndDarkTooltip />
      </ComponentCard>
      <ComponentCard title="Tooltip Placement">
        <TooltipPlacement />
      </ComponentCard>
      <ComponentCard title="White Tooltip Without Border and Arrow">
        <LightNoBorderTooltip />
      </ComponentCard>
      <ComponentCard title="Dark Tooltip Without Border and Arrow">
        <DarkNoBorderTooltip />
      </ComponentCard>
    </div>
  );
}
