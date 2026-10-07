import { useTheme } from "@/context/ThemeContext";
import type { ApexOptions } from "apexcharts";
import ReactApexChart from "react-apexcharts";

export default function RadarChartThree() {
  const { theme } = useTheme();
  const isDark = theme === "dark";

  const options: ApexOptions = {
    chart: {
      type: "radar",
      height: 380,
      toolbar: { show: false },
      fontFamily: "Outfit, sans-serif",
      background: "transparent",
    },
    labels: [
      "Sunday",
      "Monday",
      "Tuesday",
      "Wednesday",
      "Thursday",
      "Friday",
      "Saturday",
    ],
    colors: ["#465FFF"],
    fill: { opacity: 0.3 },
    stroke: { show: true, width: 2, colors: ["#465FFF"] },
    markers: { size: 0 },
    dataLabels: {
      enabled: true,
      background: {
        enabled: true,
        borderRadius: 6,
        borderWidth: 0,
        foreColor: "#465FFF",
        padding: 6,
        dropShadow: { enabled: false },
      },
      style: { fontSize: "12px", fontWeight: "600", colors: ["#ffffff"] },
      formatter: (val: string | number) => String(val),
    },
    plotOptions: {
      radar: {
        polygons: {
          strokeColors: isDark ? "#313D4F" : "#E4E7EC",
          connectorColors: isDark ? "#313D4F" : "#E4E7EC",
          fill: {
            colors: isDark ? ["#1e2d40", "#1a2535"] : ["#F2F4F7", "#ffffff"],
          },
        },
      },
    },
    yaxis: {
      show: true,
      min: 0,
      max: 140,
      tickAmount: 7,
      labels: {
        style: { fontSize: "11px", colors: "#98A2B3" },
        formatter: (val: number) => String(val),
      },
    },
    xaxis: {
      labels: {
        style: {
          fontSize: "13px",
          colors: Array(7).fill(isDark ? "#98A2B3" : "#344054"),
        },
      },
    },
    legend: { show: false },
    tooltip: { y: { formatter: (val: number) => String(val) } },
  };

  const series = [{ name: "Weekly", data: [100, 40, 60, 25, 60, 80, 20] }];

  return (
    <div className="max-w-full">
      <div id="chartThirtyNine">
        <ReactApexChart
          options={options}
          series={series}
          type="radar"
          height={380}
        />
      </div>
    </div>
  );
}
