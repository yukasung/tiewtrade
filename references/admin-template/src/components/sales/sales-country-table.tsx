import { useState } from "react";
import { useTranslation } from "react-i18next";
import { MoreDotIcon } from "../../icons";
import { Dropdown } from "../ui/dropdown/Dropdown";
import { DropdownItem } from "../ui/dropdown/DropdownItem";

const COLS = 12;
const ROWS = 12;
const BASE = [84, 61, 52, 45, 40, 37, 34, 31, 29, 27, 25, 23];
const OFFSETS = [0, 4, -3, 6, -2, 3, -5, 7, -1, 5, -3, 2];

function buildMatrix(): number[][] {
  const matrix: number[][] = [];
  for (let s = 0; s < ROWS; s++) {
    const numPeriods = s + 1;
    const row: number[] = [];
    for (let col = 0; col < COLS; col++) {
      row.push(
        col < numPeriods
          ? Math.min(100, Math.max(1, BASE[col] + OFFSETS[s]))
          : 0,
      );
    }
    matrix.push(row);
  }
  // Reverse so the fullest row (12 active cells) is at the top
  return matrix.slice().reverse();
}

function getCellColor(value: number): string {
  if (value === 0) return "transparent";
  if (value <= 25) return "#DDE9FF";
  if (value <= 50) return "#9CB9FF";
  if (value <= 75) return "#7592FF";
  return "#465FFF";
}

interface TooltipState {
  col: number;
  value: number;
  x: number;
  y: number;
}

export default function UserRetentionTable() {
  const { t } = useTranslation();
  const matrix = buildMatrix();

  const [tooltip, setTooltip] = useState<TooltipState | null>(null);

  const handleMouseEnter = (
    e: React.MouseEvent<HTMLDivElement>,
    value: number,
    col: number,
  ) => {
    if (value === 0) return;
    const rect = e.currentTarget.getBoundingClientRect();
    const wrapper = e.currentTarget.closest(
      ".hm-wrapper",
    ) as HTMLElement | null;
    const wRect = wrapper?.getBoundingClientRect();
    setTooltip({
      col,
      value,
      x: rect.left - (wRect?.left ?? 0) + rect.width / 2,
      y: rect.top - (wRect?.top ?? 0),
    });
  };

  const [isOpen, setIsOpen] = useState(false);

  function toggleDropdown() {
    setIsOpen(!isOpen);
  }

  function closeDropdown() {
    setIsOpen(false);
  }

  return (
    <div className="rounded-2xl border border-gray-200 bg-white p-5 dark:border-gray-800 dark:bg-white/3">
      {/* Header */}
      <div className="mb-4 flex items-center justify-between gap-2">
        <div>
          <h2 className="text-lg font-medium text-gray-800 dark:text-white/90">
            {t("sales.userRetention.title")}
          </h2>
          <p className="text-sm text-gray-500 dark:text-gray-400">
            {t("sales.userRetention.subtitle")}
          </p>
        </div>
        <div className="relative inline-block">
          <button className="dropdown-toggle" onClick={toggleDropdown}>
            <MoreDotIcon className="size-6 text-gray-400 hover:text-gray-700 dark:hover:text-gray-300" />
          </button>
          <Dropdown
            isOpen={isOpen}
            onClose={closeDropdown}
            className="w-40 p-2"
          >
            <DropdownItem
              onItemClick={closeDropdown}
              className="flex w-full rounded-lg text-start font-normal text-gray-500 hover:bg-gray-100 hover:text-gray-700 dark:text-gray-400 dark:hover:bg-white/5 dark:hover:text-gray-300"
            >
              {t("common.viewMore")}
            </DropdownItem>
            <DropdownItem
              onItemClick={closeDropdown}
              className="flex w-full rounded-lg text-start font-normal text-gray-500 hover:bg-gray-100 hover:text-gray-700 dark:text-gray-400 dark:hover:bg-white/5 dark:hover:text-gray-300"
            >
              {t("common.delete")}
            </DropdownItem>
          </Dropdown>
        </div>
      </div>

      {/* Stat row */}
      <div className="mb-6 flex items-center gap-2">
        <h3 className="text-3xl text-gray-800 dark:text-white/90">24%</h3>
        <span className="flex items-center text-sm text-green-600">
          <svg
            width="16"
            height="16"
            viewBox="0 0 16 16"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
          >
            <path
              d="M7.9974 2.66602L7.9974 13.3336M4 6.66334L7.99987 2.66602L12 6.66334"
              stroke="#039855"
              strokeWidth="1.5"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
          3.2%
        </span>
        <span className="text-sm text-gray-500 dark:text-gray-400">
          {t("sales.userRetention.increasedVsLastWeek")}
        </span>
      </div>

      {/* Heatmap table */}
      <div
        className="hm-wrapper relative w-full"
        onMouseLeave={() => setTooltip(null)}
      >
        {/* Tooltip */}
        {tooltip && (
          <div
            className="pointer-events-none absolute z-10 -translate-x-1/2 -translate-y-full rounded-md border border-gray-200 bg-white px-2 py-1 text-xs text-gray-700 shadow-md dark:border-gray-700 dark:bg-gray-900 dark:text-gray-200"
            style={{ left: tooltip.x, top: tooltip.y - 6 }}
          >
            <span className="font-medium"> {tooltip.col + 1}</span>:{" "}
            {tooltip.value}%
          </div>
        )}

        {/*
          table-layout: fixed  → all 12 columns share equal width
          borderCollapse: separate + borderSpacing → creates gap between cells
        */}
        <table
          className="w-full"
          style={{
            tableLayout: "fixed",
            borderCollapse: "separate",
            borderSpacing: "2px",
          }}
        >
          <tbody>
            {matrix.map((row, rowIdx) => (
              <tr key={rowIdx}>
                {row.map((value, colIdx) => (
                  <td key={colIdx} style={{ padding: 0 }}>
                    {/*
                      The colored div lives inside the td.
                      width:100% inherits the equal column width from table-layout:fixed.
                      aspect-ratio:1/1 forces height = width → perfect square.
                    */}
                    <div
                      onMouseEnter={(e) => handleMouseEnter(e, value, colIdx)}
                      style={{
                        width: "100%",
                        height: 17,
                        backgroundColor: getCellColor(value),
                        borderRadius: 1,
                        cursor: value > 0 ? "pointer" : "default",
                        transition: "opacity 0.15s ease",
                      }}
                      className={value > 0 ? "hover:opacity-75" : ""}
                    />
                  </td>
                ))}
              </tr>
            ))}
          </tbody>

          {/* X-axis labels */}
          <tfoot>
            <tr>
              {Array.from({ length: COLS }, (_, i) => (
                <td
                  key={i}
                  className="pt-2 text-center text-xs text-gray-400"
                  style={{ padding: "8px 0 0 0" }}
                >
                  {i + 1}
                </td>
              ))}
            </tr>
          </tfoot>
        </table>
      </div>
    </div>
  );
}
