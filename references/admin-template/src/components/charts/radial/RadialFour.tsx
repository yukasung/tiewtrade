import type { ApexOptions } from "apexcharts";
import { useEffect } from "react";
import ReactApexChart from "react-apexcharts";

export default function RadialFour() {
  const dataLabels = ["Loans", "Mortgage", "Savings", "Credit Card"];
  const dataValues = [20, 20, 20, 20];

  const options: ApexOptions = {
    chart: {
      type: "radialBar",
      height: 320,
      toolbar: { show: false },
      fontFamily: "Outfit, sans-serif",
    },
    colors: ["#161950", "#252DAE", "#465FFF", "#9CB9FF"],
    plotOptions: {
      radialBar: {
        startAngle: 0,
        endAngle: 360,
        hollow: {
          margin: 0,
          size: "45%",
          background: "transparent",
        },
        track: {
          show: true,
          background: "#F2F4F7",
          strokeWidth: "100%",
          margin: 0,
        },
        dataLabels: {
          show: false,
        },
      },
    },
    labels: dataLabels,
    stroke: {
      lineCap: "butt",
    },
    legend: {
      show: true,
      position: "left",
      floating: false,
      markers: {
        shape: "circle",
        size: 6,
        offsetX: -2,
        strokeWidth: 0,
      },
      formatter: (seriesName: string, opts?: { seriesIndex: number }) => {
        const pct = opts ? dataValues[opts.seriesIndex] : "";
        return `${seriesName} &nbsp;&nbsp; <strong>${pct}%</strong>`;
      },
      itemMargin: {
        vertical: 6,
      },
      labels: {
        colors: "#344054",
      },
      fontSize: "13px",
    },
    tooltip: {
      enabled: true,
      custom: ({
        seriesIndex,
        w,
      }: {
        seriesIndex: number;
        w: { globals: { labels: string[]; colors: string[] } };
      }) => {
        const label = w.globals.labels[seriesIndex];
        const pct = dataValues[seriesIndex];
        const color = w.globals.colors[seriesIndex];
        return `<div style="display:flex;align-items:center;gap:8px;padding:8px 12px;border-radius:8px;border:1px solid #E4E7EC;background:#fff;box-shadow:0 1px 4px rgba(0,0,0,0.08);font-family:Outfit,sans-serif;font-size:13px;">
          <span style="width:10px;height:10px;border-radius:50%;background:${color};display:inline-block;flex-shrink:0;"></span>
          <span style="color:#667085;">${label}:</span>
          <strong style="color:#101828;">${pct}%</strong>
        </div>`;
      },
    },
  };

  const series = [80, 80, 80, 80];

  useEffect(() => {
    const style = document.createElement("style");
    style.textContent = `
      #chartFortyThree .apexcharts-tooltip {
        background: transparent !important;
        border: none !important;
        box-shadow: none !important;
        padding: 0 !important;
      }
    `;
    document.head.appendChild(style);
    return () => {
      document.head.removeChild(style);
    };
  }, []);

  return (
    <div className="max-w-full">
      <div id="chartFortyThree">
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
