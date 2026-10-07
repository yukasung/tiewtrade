import type { ApexOptions } from "apexcharts";
import ReactApexChart from "react-apexcharts";

export default function RadialThree() {
  const options: ApexOptions = {
    chart: {
      type: "radialBar",
      height: 320,
      toolbar: { show: false },
      fontFamily: "Outfit, sans-serif",
    },
    colors: ["#FCE7F6", "#BDB4FE", "#7A5AF8", "#4E5BA6"],
    plotOptions: {
      radialBar: {
        startAngle: 0,
        endAngle: 360,
        hollow: {
          size: "50%",
          background: "transparent",
        },
        track: {
          background: "#F2F4F7",
          strokeWidth: "100%",
          margin: 4,
        },
        dataLabels: {
          name: {
            show: true,
            fontSize: "14px",
            fontWeight: "500",
            color: "#667085",
            offsetY: -4,
          },
          value: {
            show: true,
            fontSize: "22px",
            fontWeight: "700",
            color: "#101828",
            offsetY: 14,
            formatter: () => "62.25%",
          },
          total: {
            show: true,
            label: "Total",
            fontSize: "14px",
            fontWeight: "500",
            color: "#667085",
            formatter: () => "62.25%",
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

  const series = [62.25, 75, 50, 35];

  return (
    <div className="max-w-full">
      <div id="chartFortyTwo">
        <ReactApexChart
          options={options}
          series={series}
          type="radialBar"
          height={320}
        />
      </div>
    </div>
  );
}
