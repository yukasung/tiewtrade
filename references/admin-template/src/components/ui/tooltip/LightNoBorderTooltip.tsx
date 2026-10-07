import Tooltip from "./Tooltip";

export default function LightNoBorderTooltip() {
  return (
    <div className="flex flex-wrap items-center gap-4">
      <Tooltip content="This is a tooltip" placement="top" variant="light">
        <button className="inline-flex px-4 py-3 text-sm font-medium text-white rounded-lg bg-brand-500 shadow-theme-xs">
          Tooltip Top
        </button>
      </Tooltip>
      <Tooltip content="This is a tooltip" placement="right" variant="light">
        <button className="inline-flex px-4 py-3 text-sm font-medium text-white rounded-lg bg-brand-500 shadow-theme-xs">
          Tooltip Right
        </button>
      </Tooltip>
      <Tooltip content="This is a tooltip" placement="left" variant="light">
        <button className="inline-flex px-4 py-3 text-sm font-medium text-white rounded-lg bg-brand-500 shadow-theme-xs">
          Tooltip Left
        </button>
      </Tooltip>
      <Tooltip content="This is a tooltip" placement="bottom" variant="light">
        <button className="inline-flex px-4 py-3 text-sm font-medium text-white rounded-lg bg-brand-500 shadow-theme-xs">
          Tooltip Bottom
        </button>
      </Tooltip>
    </div>
  );
}
