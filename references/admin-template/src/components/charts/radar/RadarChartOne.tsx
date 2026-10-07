import { useTheme } from "@/context/ThemeContext";
import type { ApexOptions } from "apexcharts";
import ReactApexChart from "react-apexcharts";

export default function RadarChartOne() {
  const { theme } = useTheme();
  const isDark = theme === "dark";

  const options: ApexOptions = {
    chart: {
      type: "radar",
      height: 320,
      toolbar: { show: false },
      fontFamily: "Outfit, sans-serif",
      background: "transparent",
    },
    labels: [
      "Estonia",
      "Germany",
      "France",
      "Spain",
      "Italy",
      "Canada",
      "Japan",
      "Brazil",
    ],
    colors: ["#465FFF"],
    fill: { opacity: 0.3 },
    stroke: { show: true, width: 3, colors: ["#465FFF"] },
    markers: {
      size: 4,
      colors: ["#465FFF"],
      strokeColors: isDark ? "#1D2939" : "#fff",
      strokeWidth: 2,
    },
    dataLabels: { enabled: false },
    plotOptions: {
      radar: {
        polygons: {
          strokeColors: isDark ? "#313D4F" : "#E4E7EC",
          connectorColors: isDark ? "#313D4F" : "#E4E7EC",
          fill: {
            colors: isDark ? ["#1e2d40", "#1a2535"] : ["#ffffff", "#ffffff"],
          },
        },
      },
    },
    yaxis: {
      show: true,
      min: 0,
      max: 9,
      tickAmount: 3,
      labels: {
        style: { fontSize: "11px", colors: "#98A2B3" },
        formatter: (val: number) => String(val),
      },
    },
    xaxis: {
      labels: {
        style: {
          fontSize: "13px",
          colors: Array(8).fill(isDark ? "#98A2B3" : "#344054"),
        },
      },
    },
    legend: { show: false },
    tooltip: { y: { formatter: (val: number) => String(val) } },
  };

  const series = [{ name: "Data", data: [9, 7, 3, 5, 3, 4, 6, 8] }];

  return (
    <div className="max-w-full">
      <div id="chartThirtySeven">
        <ReactApexChart
          options={options}
          series={series}
          type="radar"
          height={320}
        />
      </div>
    </div>
  );
}
