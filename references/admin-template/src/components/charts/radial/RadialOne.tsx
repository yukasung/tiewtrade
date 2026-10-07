import type { ApexOptions } from "apexcharts";
import ReactApexChart from "react-apexcharts";

export default function RadialOne() {
  const options: ApexOptions = {
    chart: {
      type: "radialBar",
      height: 300,
      toolbar: { show: false },
      fontFamily: "Outfit, sans-serif",
    },
    colors: ["#465FFF"],
    plotOptions: {
      radialBar: {
        startAngle: 0,
        endAngle: 360,
        hollow: {
          size: "72%",
          background: "transparent",
        },
        track: {
          background: "#F2F4F7",
          strokeWidth: "100%",
          startAngle: 0,
          endAngle: 360,
        },
        dataLabels: {
          name: {
            show: true,
            fontSize: "15px",
            fontWeight: "600",
            color: "#344054",
            offsetY: -4,
          },
          value: {
            show: true,
            fontSize: "20px",
            fontWeight: "700",
            color: "#101828",
            offsetY: 16,
            formatter: (val: number) => `${val}%`,
          },
        },
      },
    },
    stroke: {
      lineCap: "butt",
    },
    legend: {
      show: false,
    },
    tooltip: {
      enabled: false,
    },
  };

  const series = [62.25];

  return (
    <div className="max-w-full">
      <div id="chartForty">
        <ReactApexChart
          options={options}
          series={series}
          type="radialBar"
          height={300}
        />
      </div>
    </div>
  );
}
