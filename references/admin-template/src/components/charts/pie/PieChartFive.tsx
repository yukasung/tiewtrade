import { useTheme } from "@/context/ThemeContext";
import type { ApexOptions } from "apexcharts";
import ReactApexChart from "react-apexcharts";

export default function PieChartFive() {
  const { theme } = useTheme();
  const isDark = theme === "dark";

  const options: ApexOptions = {
    chart: {
      type: "donut",
      height: 280,
      toolbar: { show: false },
      fontFamily: "Outfit, sans-serif",
    },
    labels: ["Email", "Social Media", "Mobile", "Direct", "Other"],
    colors: ["#4E5BA6", "#4E5BA6", "#BDB4FE", "#B9E6FE", "#FCE7F6"],
    plotOptions: {
      pie: {
        startAngle: -90,
        endAngle: 90,
        offsetY: 10,
        donut: {
          size: "55%",
        },
      },
    },
    dataLabels: {
      enabled: false,
    },
    stroke: {
      show: true,
      width: 3,
      colors: [isDark ? "#1D2939" : "#ffffff"],
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
        horizontal: 10,
        vertical: 0,
      },
      labels: {
        colors: isDark ? "#98A2B3" : "#344054",
      },
      fontSize: "13px",
    },
    tooltip: {
      enabled: false,
    },
    responsive: [
      {
        breakpoint: 480,
        options: {
          chart: { height: 240 },
        },
      },
    ],
  };

  const series = [35, 25, 20, 12, 8];

  return (
    <div className="max-w-full">
      <div id="chartFortyFour">
        <ReactApexChart
          options={options}
          series={series}
          type="donut"
          height={280}
        />
      </div>
    </div>
  );
}
