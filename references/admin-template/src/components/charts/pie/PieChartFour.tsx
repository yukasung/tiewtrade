import type { ApexOptions, ApexTooltipCustomOpts } from "apexcharts";
import ReactApexChart from "react-apexcharts";

export default function PieChartFour() {
  const options: ApexOptions = {
    chart: {
      type: "pie",
      height: 300,
      toolbar: { show: false },
      fontFamily: "Outfit, sans-serif",
    },
    labels: ["Image", "Video", "Audio", "Documents"],
    colors: ["#C2D6FF", "#9CB9FF", "#465FFF", "#2D3282"],
    dataLabels: {
      enabled: false,
    },
    stroke: {
      show: false,
      width: 0,
    },
    legend: {
      show: true,
      position: "bottom",
      horizontalAlign: "center",
      markers: {
        shape: "circle",
        size: 6,
        offsetX: -2,
        strokeWidth: 0,
      },
      itemMargin: {
        horizontal: 12,
        vertical: 0,
      },
      labels: {
        colors: "#344054",
      },
      fontSize: "14px",
      onItemHover: {
        highlightDataSeries: true,
      },
    },
    tooltip: {
      enabled: true,
      custom: ({
        series,
        seriesIndex,
        w,
      }: ApexTooltipCustomOpts) => {
        const label = (w.config.labels as string[])[seriesIndex];
        const rawVal = series[seriesIndex];
        const value = Array.isArray(rawVal) ? rawVal[0] : rawVal;
        const color = (w.config.colors as string[])[seriesIndex];
        return `<div class="flex items-center gap-2 px-3 py-2 rounded-lg border border-gray-200 bg-white shadow-sm dark:border-gray-700 dark:bg-gray-800" style="font-family: Outfit, sans-serif; font-size: 13px;">
          <span style="width:10px;height:10px;border-radius:50%;background:${color};display:inline-block;flex-shrink:0;"></span>
          <span class="text-gray-600 dark:text-gray-400">${label}:</span>
          <strong class="text-gray-900 dark:text-white">${value}%</strong>
        </div>`;
      },
    },
    responsive: [
      {
        breakpoint: 480,
        options: {
          chart: {
            height: 260,
          },
        },
      },
    ],
  };

  const series = [28, 22, 18, 32];

  return (
    <div className="max-w-full">
      <div id="chartThirtySix" className="api-token-chart">
        <ReactApexChart
          options={options}
          series={series}
          type="pie"
          height={300}
        />
      </div>
    </div>
  );
}
