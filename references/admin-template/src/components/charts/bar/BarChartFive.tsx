import type { ApexOptions } from "apexcharts";
import ReactApexChart from "react-apexcharts";

export default function BarChartFive() {
  const options: ApexOptions = {
    chart: {
      type: "bar",
      height: 300,
      toolbar: { show: false },
      fontFamily: "Outfit, sans-serif",
    },
    plotOptions: {
      bar: {
        horizontal: false,
        columnWidth: "50%",
        borderRadius: 4,
        borderRadiusApplication: "end",
      },
    },
    dataLabels: {
      enabled: false,
    },
    stroke: {
      show: true,
      width: 4,
      colors: ["transparent"],
    },
    colors: ["#C2D6FF", "#465FFF"],
    xaxis: {
      categories: [
        "Jan",
        "Feb",
        "Mar",
        "Apr",
        "May",
        "Jun",
        "Jul",
        "Aug",
        "Sep",
        "Oct",
        "Nov",
        "Dec",
      ],
      axisTicks: {
        show: false,
      },
      axisBorder: {
        show: false,
      },
    },
    yaxis: {
      labels: {
        formatter: (val: number) => `${val}%`,
        style: {
          fontSize: "12px",
          colors: "#344054",
        },
      },
      max: 100,
    },
    fill: {
      opacity: 1,
    },
    tooltip: {
      y: {
        formatter: (val: number) => `${val}%`,
      },
    },
    legend: {
      show: false,
    },
    grid: {
      borderColor: "#F2F4F7",
      strokeDashArray: 0,
    },
  };

  const series = [
    {
      name: "2023",
      data: [80, 60, 70, 40, 65, 45, 48, 55, 58, 50, 67, 75],
    },
    {
      name: "2024",
      data: [90, 50, 65, 25, 78, 68, 75, 90, 30, 70, 90, 95],
    },
  ];

  return (
    <div className="custom-scrollbar max-w-full overflow-x-auto">
      <div id="chartThirtyFive" className="min-w-250 2xl:min-w-full">
        <ReactApexChart
          options={options}
          series={series}
          type="bar"
          height={300}
        />
      </div>
    </div>
  );
}
