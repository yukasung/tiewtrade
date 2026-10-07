import { useTheme } from "@/context/ThemeContext";
import type { ApexOptions } from "apexcharts";
import ReactApexChart from "react-apexcharts";

export default function BarChartFour() {
  const { theme } = useTheme();
  const options: ApexOptions = {
    colors: ["#7592FF", "#7CD4FD", "#BDB4FE", "#FE9EFE", "#6FEAA6", "#D0D5DD"],
    chart: {
      fontFamily: "Outfit, sans-serif",
      type: "bar",
      height: 50,
      width: "100%",
      stacked: true,
      toolbar: {
        show: false,
      },
      animations: {
        enabled: false,
      },
    },
    plotOptions: {
      bar: {
        horizontal: true,
        barHeight: "32px",
        borderRadius: 4,
        borderRadiusApplication: "end",
      },
    },
    dataLabels: {
      enabled: false,
    },
    grid: {
      show: false,
      padding: {
        top: -30,
        bottom: -20,
        left: -10,
        right: 0,
      },
    },
    xaxis: {
      labels: {
        show: false,
      },
      axisBorder: {
        show: false,
      },
      axisTicks: {
        show: false,
      },
    },
    yaxis: {
      labels: {
        show: false,
      },
    },
    legend: {
      show: false,
    },
    tooltip: {
      enabled: true,
      x: {
        show: false,
      },
    },
    stroke: {
      show: true,
      width: 1,
      colors: [theme === "dark" ? "#111827" : "#ffffff"],
    },
    states: {
      hover: {
        filter: {
          type: "none",
        },
      },
      active: {
        filter: {
          type: "none",
        },
      },
    },
  };

  const series = [
    {
      name: "Activity",
      data: [45],
    },
    {
      name: "Online Purchases",
      data: [25],
    },
    {
      name: "Groceries",
      data: [15],
    },
    {
      name: "Digital Goods",
      data: [20],
    },
    {
      name: "Stationery",
      data: [10],
    },
    {
      name: "Others",
      data: [30],
    },
  ];

  return (
    <div>
      <ReactApexChart
        options={options}
        series={series}
        type="bar"
        height={50}
      />
    </div>
  );
}
