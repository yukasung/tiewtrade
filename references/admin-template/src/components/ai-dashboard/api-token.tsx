import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Dropdown } from "../ui/dropdown/Dropdown";
import { DropdownItem } from "../ui/dropdown/DropdownItem";
import { MoreDotIcon } from "../../icons";
import Chart from "react-apexcharts";

function formatConfiguredKey(template: string, count: number): string {
  const pluralMatch = template.match(/\{count,\s*plural,\s*(.+)\}/);
  if (!pluralMatch) return template.replace(/\{count\}/g, String(count));
  const rules = pluralMatch[1];
  const map: Record<string, string> = {};
  const regex = /(\w+)\s*\{([^}]*)\}/g;
  let m;
  while ((m = regex.exec(rules)) !== null) {
    map[m[1]] = m[2];
  }
  let result = map.other || "";
  if (count === 1 && map.one) {
    result = map.one;
  } else if (count === 2 && map.two) {
    result = map.two;
  } else if (count >= 3 && count <= 10 && map.few) {
    result = map.few;
  } else if (map.many && count > 10) {
    result = map.many;
  }
  return result.replace(/#/g, String(count)).replace(/\{count\}/g, String(count));
}

export default function ApiToken() {
  const { t } = useTranslation();
  const [isOpen, setIsOpen] = useState(false);

  function toggleDropdown() {
    setIsOpen(!isOpen);
  }

  function closeDropdown() {
    setIsOpen(false);
  }

  const series = [900, 700, 850];

  const options = {
    colors: ["#7592FF", "#7CD4FD", "#BDB4FE"],
    labels: [" GPT", "Gemini ", "xAI"],
    chart: {
      fontFamily: "Outfit, sans-serif",
      type: "donut" as const,
    },
    stroke: {
      show: false,
      width: 4,
      colors: ["transparent"],
    },
    plotOptions: {
      pie: {
        donut: {
          size: "70%",
          labels: {
            show: true,
            name: {
              show: true,
              offsetY: 0,
              color: "#1D2939",
              fontSize: "12px",
            },
            value: {
              show: true,
              offsetY: 10,
              color: "#667085",
              fontSize: "12px",
              formatter: () => "Total API Token Used",
            },
            total: {
              show: true,
              label: "13.5M",
              color: "#000000",
              fontSize: "24px",
              fontWeight: 600,
            },
          },
        },
      },
    },
    dataLabels: {
      enabled: false,
    },
    tooltip: {
      enabled: true,
      custom: function ({ series, seriesIndex, w }: any) {
        return (
          '<div class="rounded-lg border border-gray-200 bg-white p-2 shadow-sm dark:border-gray-800 dark:bg-gray-900">' +
          '<div class="flex items-center gap-2">' +
          ' <div class="size-2 rounded-full" style="background-color: ' +
          w.config.colors[seriesIndex] +
          '"></div>' +
          ' <span class="text-xs font-medium text-gray-800 dark:text-white/90">' +
          w.config.labels[seriesIndex] +
          "</span>" +
          "</div>" +
          '<div class="mt-1 text-xs text-gray-500 dark:text-gray-400">' +
          series[seriesIndex] +
          " Units" +
          "</div>" +
          "</div>"
        );
      },
    },
    legend: {
      show: false,
    },
    responsive: [
      {
        breakpoint: 640,
        options: {
          chart: {
            width: "100%",
            height: 280,
          },
        },
      },
    ],
  };
  return (
    <div className="rounded-2xl border border-gray-200 bg-white px-3 py-2 dark:border-gray-800 dark:bg-white/3">
      <div className="mb-3 flex items-center justify-between gap-5 px-4 pt-4">
        <div>
          <h3 className="text-lg font-semibold text-gray-800 dark:text-white/90">
            {t("aiDashboard.apiToken.title")}
          </h3>
        </div>
        <div className="relative inline-block">
          <button className="dropdown-toggle" onClick={toggleDropdown}>
            <MoreDotIcon className="text-gray-400 hover:text-gray-700 dark:hover:text-gray-300 size-6" />
          </button>
          <Dropdown
            isOpen={isOpen}
            onClose={closeDropdown}
            className="w-40 p-2"
          >
            <DropdownItem
              onItemClick={closeDropdown}
              className="flex w-full font-normal text-start text-gray-500 rounded-lg hover:bg-gray-100 hover:text-gray-700 dark:text-gray-400 dark:hover:bg-white/5 dark:hover:text-gray-300"
            >
              {t("common.viewMore")}
            </DropdownItem>
            <DropdownItem
              onItemClick={closeDropdown}
              className="flex w-full font-normal text-start text-gray-500 rounded-lg hover:bg-gray-100 hover:text-gray-700 dark:text-gray-400 dark:hover:bg-white/5 dark:hover:text-gray-300"
            >
              {t("common.delete")}
            </DropdownItem>
          </Dropdown>
        </div>
      </div>
      <div className="flex flex-col gap-6">
        <div className="flex justify-center api-token-chart">
          {/* Chart */}
          <Chart options={options} series={series} type="donut" width="100%" />
        </div>
        <div>
          <ul className="divide-y divide-gray-100 border-y border-gray-100 dark:divide-gray-800 dark:border-gray-800">
            <li className="flex items-center justify-between px-4 py-3">
              {/* <!-- Left --> */}
              <div className="flex items-center gap-3">
                <div className="flex size-10 items-center justify-center rounded-full border border-gray-200 dark:border-gray-800">
                  <svg
                    className="hidden dark:block"
                    width="23"
                    height="22"
                    viewBox="0 0 23 22"
                    fill="none"
                    xmlns="http://www.w3.org/2000/svg"
                  >
                    <path
                      d="M8.51399 8.00796V5.91795C8.51399 5.74192 8.58003 5.60984 8.73397 5.52194L12.9361 3.10197C13.5081 2.77199 14.1901 2.61806 14.894 2.61806C17.5341 2.61806 19.2061 4.66411 19.2061 6.84203C19.2061 6.99598 19.2061 7.17201 19.184 7.34803L14.828 4.79597C14.5641 4.64204 14.3 4.64204 14.036 4.79597L8.51399 8.00796ZM18.326 16.1481V11.1539C18.326 10.8458 18.1939 10.6259 17.93 10.4719L12.408 7.25993L14.212 6.22586C14.3659 6.13795 14.498 6.13795 14.652 6.22586L18.8541 8.64584C20.0642 9.34993 20.878 10.8458 20.878 12.2978C20.878 13.9697 19.8882 15.5098 18.326 16.1478V16.1481ZM7.216 11.748L5.412 10.6921C5.25806 10.6042 5.19203 10.4721 5.19203 10.2961V5.45613C5.19203 3.10218 6.99602 1.32005 9.43808 1.32005C10.3622 1.32005 11.22 1.62816 11.9462 2.1781L7.61222 4.68619C7.34828 4.84014 7.21621 5.06012 7.21621 5.36823V11.7482L7.216 11.748ZM11.0991 13.992L8.51398 12.5401V9.46013L11.0991 8.00819L13.6839 9.46013V12.5401L11.0991 13.992ZM12.76 20.6801C11.836 20.6801 10.9781 20.372 10.252 19.8221L14.5859 17.3139C14.8498 17.16 14.9819 16.9401 14.9819 16.632V10.2519L16.808 11.3079C16.962 11.3958 17.028 11.5278 17.028 11.7039V16.5439C17.028 18.8977 15.2018 20.68 12.76 20.68V20.6801ZM7.54596 15.7741L3.34385 13.3541C2.13375 12.65 1.31988 11.1541 1.31988 9.7022C1.31988 8.00819 2.33188 6.4902 3.8938 5.85214V10.8681C3.8938 11.1762 4.02587 11.3962 4.28981 11.5502L9.78993 14.74L7.98593 15.7741C7.83198 15.8621 7.6999 15.8621 7.54596 15.7741ZM7.3041 19.3822C4.81809 19.3822 2.99201 17.512 2.99201 15.2021C2.99201 15.026 3.01408 14.85 3.03597 14.674L7.36993 17.1821C7.63387 17.336 7.89801 17.336 8.16195 17.1821L13.6839 13.9922V16.0823C13.6839 16.2583 13.6179 16.3903 13.464 16.4782L9.26184 18.8982C8.68983 19.2281 8.00779 19.3822 7.3039 19.3822L7.3041 19.3822ZM12.76 22C15.422 22 17.6439 20.108 18.1502 17.6C20.6141 16.9619 22.1982 14.6519 22.1982 12.298C22.1982 10.7579 21.5382 9.26204 20.3501 8.18401C20.4601 7.72197 20.5263 7.25993 20.5263 6.7981C20.5263 3.65215 17.9742 1.29799 15.0261 1.29799C14.4322 1.29799 13.8602 1.3859 13.2881 1.58401C12.298 0.615974 10.934 0 9.43808 0C6.77604 0 4.55416 1.89191 4.04795 4.39999C1.58403 5.03804 0 7.34804 0 9.70198C0 11.242 0.659934 12.7379 1.84795 13.816C1.73795 14.278 1.67192 14.74 1.67192 15.2019C1.67192 18.3478 4.22396 20.7019 7.17204 20.7019C7.76593 20.7019 8.33797 20.6141 8.90999 20.416C9.89989 21.384 11.2639 22 12.76 22Z"
                      fill="white"
                      fillOpacity="0.9"
                    />
                  </svg>
                  <svg
                    className="block dark:hidden"
                    width="23"
                    height="22"
                    viewBox="0 0 23 22"
                    fill="none"
                    xmlns="http://www.w3.org/2000/svg"
                  >
                    <path
                      d="M8.51399 8.00796V5.91795C8.51399 5.74192 8.58003 5.60984 8.73397 5.52194L12.9361 3.10197C13.5081 2.77199 14.1901 2.61806 14.894 2.61806C17.5341 2.61806 19.2061 4.66411 19.2061 6.84203C19.2061 6.99598 19.2061 7.17201 19.184 7.34803L14.828 4.79597C14.5641 4.64204 14.3 4.64204 14.036 4.79597L8.51399 8.00796ZM18.326 16.1481V11.1539C18.326 10.8458 18.1939 10.6259 17.93 10.4719L12.408 7.25993L14.212 6.22586C14.3659 6.13795 14.498 6.13795 14.652 6.22586L18.8541 8.64584C20.0642 9.34993 20.878 10.8458 20.878 12.2978C20.878 13.9697 19.8882 15.5098 18.326 16.1478V16.1481ZM7.216 11.748L5.412 10.6921C5.25806 10.6042 5.19203 10.4721 5.19203 10.2961V5.45613C5.19203 3.10218 6.99602 1.32005 9.43808 1.32005C10.3622 1.32005 11.22 1.62816 11.9462 2.1781L7.61222 4.68619C7.34828 4.84014 7.21621 5.06012 7.21621 5.36823V11.7482L7.216 11.748ZM11.0991 13.992L8.51398 12.5401V9.46013L11.0991 8.00819L13.6839 9.46013V12.5401L11.0991 13.992ZM12.76 20.6801C11.836 20.6801 10.9781 20.372 10.252 19.8221L14.5859 17.3139C14.8498 17.16 14.9819 16.9401 14.9819 16.632V10.2519L16.808 11.3079C16.962 11.3958 17.028 11.5278 17.028 11.7039V16.5439C17.028 18.8977 15.2018 20.68 12.76 20.68V20.6801ZM7.54596 15.7741L3.34385 13.3541C2.13375 12.65 1.31988 11.1541 1.31988 9.7022C1.31988 8.00819 2.33188 6.4902 3.8938 5.85214V10.8681C3.8938 11.1762 4.02587 11.3962 4.28981 11.5502L9.78993 14.74L7.98593 15.7741C7.83198 15.8621 7.6999 15.8621 7.54596 15.7741ZM7.3041 19.3822C4.81809 19.3822 2.99201 17.512 2.99201 15.2021C2.99201 15.026 3.01408 14.85 3.03597 14.674L7.36993 17.1821C7.63387 17.336 7.89801 17.336 8.16195 17.1821L13.6839 13.9922V16.0823C13.6839 16.2583 13.6179 16.3903 13.464 16.4782L9.26184 18.8982C8.68983 19.2281 8.00779 19.3822 7.3039 19.3822L7.3041 19.3822ZM12.76 22C15.422 22 17.6439 20.108 18.1502 17.6C20.6141 16.9619 22.1982 14.6519 22.1982 12.298C22.1982 10.7579 21.5382 9.26204 20.3501 8.18401C20.4601 7.72197 20.5263 7.25993 20.5263 6.7981C20.5263 3.65215 17.9742 1.29799 15.0261 1.29799C14.4322 1.29799 13.8602 1.3859 13.2881 1.58401C12.298 0.615974 10.934 0 9.43808 0C6.77604 0 4.55416 1.89191 4.04795 4.39999C1.58403 5.03804 0 7.34804 0 9.70198C0 11.242 0.659934 12.7379 1.84795 13.816C1.73795 14.278 1.67192 14.74 1.67192 15.2019C1.67192 18.3478 4.22396 20.7019 7.17204 20.7019C7.76593 20.7019 8.33797 20.6141 8.90999 20.416C9.89989 21.384 11.2639 22 12.76 22Z"
                      fill="#1D2939"
                    />
                  </svg>
                </div>

                <div>
                  <p className="font-medium text-gray-800 dark:text-white/90">
                    GPT
                  </p>
                  <p className="text-sm text-gray-500 dark:text-gray-400">
                    {formatConfiguredKey(t("aiDashboard.apiToken.configuredKey"), 2)}
                  </p>
                </div>
              </div>
              {/* <!-- Right --> */}
              <div className="text-end">
                <div className="flex items-center justify-end gap-1">
                  <span className="bg-brand-400 size-[5px] rounded-full"></span>
                  <span className="text-sm font-medium text-gray-700 dark:text-gray-400">
                    7M
                  </span>
                </div>
                <p className="text-xs text-gray-500 dark:text-gray-400">
                  {t("aiDashboard.apiToken.tokenUsed")}
                </p>
              </div>
            </li>
            <li className="flex items-center justify-between px-4 py-3">
              {/* <!-- Left --> */}
              <div className="flex items-center gap-3">
                <div className="flex size-10 items-center justify-center rounded-full border border-gray-200 dark:border-gray-800">
                  <svg
                    width={22}
                    height={22}
                    viewBox="0 0 22 22"
                    fill="none"
                    xmlns="http://www.w3.org/2000/svg"
                  >
                    <mask
                      id="mask0_6186_74474"
                      style={{ maskType: "alpha" }}
                      maskUnits="userSpaceOnUse"
                      x={0}
                      y={0}
                      width={22}
                      height={22}
                    >
                      <path
                        d="M11 0C11.2307 0 11.4314 0.157567 11.4877 0.381388C11.6602 1.06599 11.8853 1.73375 12.1654 2.38334C12.895 4.07828 13.8961 5.56183 15.1672 6.83288C16.4388 8.10391 17.9218 9.10504 19.6167 9.83466C20.2668 10.1147 20.934 10.3398 21.6186 10.5123C21.8424 10.5686 22 10.7693 22 11C22 11.2307 21.8425 11.4314 21.6186 11.4877C20.934 11.6602 20.2662 11.8853 19.6167 12.1654C17.9217 12.895 16.4382 13.8961 15.1672 15.1672C13.8961 16.4388 12.895 17.9217 12.1654 19.6167C11.8853 20.2669 11.6602 20.934 11.4877 21.6186C11.4314 21.8425 11.2307 22 11 22C10.7693 22 10.5686 21.8424 10.5123 21.6186C10.3398 20.934 10.1147 20.2662 9.83466 19.6167C9.10504 17.9218 8.10452 16.4382 6.83288 15.1672C5.56118 13.8961 4.07828 12.895 2.38334 12.1654C1.73313 11.8853 1.06599 11.6602 0.381388 11.4877C0.157567 11.4314 0 11.2307 0 11C2.94144e-05 10.7693 0.157581 10.5686 0.381388 10.5123C1.066 10.3398 1.73375 10.1148 2.38334 9.83466C4.07831 9.10501 5.56183 8.10394 6.83288 6.83288C8.10394 5.56183 9.10501 4.07831 9.83466 2.38334C10.1148 1.73313 10.3398 1.066 10.5123 0.381388C10.5686 0.157581 10.7693 2.94144e-05 11 0Z"
                        fill="black"
                      />
                      <path
                        d="M11 0C11.2307 0 11.4314 0.157567 11.4877 0.381388C11.6602 1.06599 11.8853 1.73375 12.1654 2.38334C12.895 4.07828 13.8961 5.56183 15.1672 6.83288C16.4388 8.10391 17.9218 9.10504 19.6167 9.83466C20.2668 10.1147 20.934 10.3398 21.6186 10.5123C21.8424 10.5686 22 10.7693 22 11C22 11.2307 21.8425 11.4314 21.6186 11.4877C20.934 11.6602 20.2662 11.8853 19.6167 12.1654C17.9217 12.895 16.4382 13.8961 15.1672 15.1672C13.8961 16.4388 12.895 17.9217 12.1654 19.6167C11.8853 20.2669 11.6602 20.934 11.4877 21.6186C11.4314 21.8425 11.2307 22 11 22C10.7693 22 10.5686 21.8424 10.5123 21.6186C10.3398 20.934 10.1147 20.2662 9.83466 19.6167C9.10504 17.9218 8.10452 16.4382 6.83288 15.1672C5.56118 13.8961 4.07828 12.895 2.38334 12.1654C1.73313 11.8853 1.06599 11.6602 0.381388 11.4877C0.157567 11.4314 0 11.2307 0 11C2.94144e-05 10.7693 0.157581 10.5686 0.381388 10.5123C1.066 10.3398 1.73375 10.1148 2.38334 9.83466C4.07831 9.10501 5.56183 8.10394 6.83288 6.83288C8.10394 5.56183 9.10501 4.07831 9.83466 2.38334C10.1148 1.73313 10.3398 1.066 10.5123 0.381388C10.5686 0.157581 10.7693 2.94144e-05 11 0Z"
                        fill="url(#paint0_linear_6186_74474)"
                      />
                    </mask>
                    <g mask="url(#mask0_6186_74474)">
                      <g filter="url(#filter0_f_6186_74474)">
                        <path
                          d="M-1.98567 17.1996C0.556267 18.1023 3.47789 16.4097 4.53996 13.4191C5.60202 10.4284 4.40235 7.2722 1.8604 6.36948C-0.681537 5.46675 -3.60316 7.15936 -4.66523 10.15C-5.72729 13.1407 -4.52762 16.2969 -1.98567 17.1996Z"
                          fill="#FFE432"
                        />
                      </g>
                      <g filter="url(#filter1_f_6186_74474)">
                        <path
                          d="M9.29967 7.33923C12.7918 7.33923 15.6228 4.44603 15.6228 0.877089C15.6228 -2.69185 12.7918 -5.58505 9.29967 -5.58505C5.80752 -5.58505 2.97656 -2.69185 2.97656 0.877089C2.97656 4.44603 5.80752 7.33923 9.29967 7.33923Z"
                          fill="#FC413D"
                        />
                      </g>
                      <g filter="url(#filter2_f_6186_74474)">
                        <path
                          d="M6.84287 28.0053C10.4883 27.8271 13.2563 23.8543 13.0255 19.1318C12.7946 14.4093 9.65228 10.7255 6.00686 10.9037C2.36144 11.0819 -0.406604 15.0547 -0.175747 19.7772C0.0551095 24.4997 3.19745 28.1835 6.84287 28.0053Z"
                          fill="#00B95C"
                        />
                      </g>
                      <g filter="url(#filter3_f_6186_74474)">
                        <path
                          d="M6.84287 28.0053C10.4883 27.8271 13.2563 23.8543 13.0255 19.1318C12.7946 14.4093 9.65228 10.7255 6.00686 10.9037C2.36144 11.0819 -0.406604 15.0547 -0.175747 19.7772C0.0551095 24.4997 3.19745 28.1835 6.84287 28.0053Z"
                          fill="#00B95C"
                        />
                      </g>
                      <g filter="url(#filter4_f_6186_74474)">
                        <path
                          d="M10.4935 25.1484C13.5497 23.289 14.3676 19.0542 12.3206 15.6897C10.2735 12.3252 6.13654 11.1051 3.08044 12.9645C0.0243359 14.824 -0.793644 19.0588 1.25343 22.4233C3.3005 25.7878 7.43744 27.0079 10.4935 25.1484Z"
                          fill="#00B95C"
                        />
                      </g>
                      <g filter="url(#filter5_f_6186_74474)">
                        <path
                          d="M22.8466 14.5754C26.2816 14.5754 29.0662 11.8939 29.0662 8.58612C29.0662 5.27834 26.2816 2.59686 22.8466 2.59686C19.4116 2.59686 16.627 5.27834 16.627 8.58612C16.627 11.8939 19.4116 14.5754 22.8466 14.5754Z"
                          fill="#3186FF"
                        />
                      </g>
                      <g filter="url(#filter6_f_6186_74474)">
                        <path
                          d="M-4.42889 13.8804C-1.26611 16.2856 3.35438 15.531 5.89126 12.195C8.42814 8.85899 7.92075 4.20486 4.75797 1.79968C1.59519 -0.605489 -3.0253 0.149091 -5.56218 3.48509C-8.09906 6.82108 -7.59167 11.4752 -4.42889 13.8804Z"
                          fill="#FBBC04"
                        />
                      </g>
                      <g filter="url(#filter7_f_6186_74474)">
                        <path
                          d="M11.7777 17.4356C15.5529 20.0311 20.5569 19.308 22.9546 15.8206C25.3523 12.3332 24.2356 7.40197 20.4605 4.80647C16.6854 2.21097 11.6813 2.93403 9.28362 6.42147C6.88594 9.90892 8.00259 14.8401 11.7777 17.4356Z"
                          fill="#3186FF"
                        />
                      </g>
                      <g filter="url(#filter8_f_6186_74474)">
                        <path
                          d="M18.6401 -0.791927C19.6006 0.513888 18.3665 3.05281 15.8837 4.87891C13.4009 6.70503 10.6096 7.12679 9.64918 5.82099C8.68873 4.51518 9.92287 1.97625 12.4056 0.150147C14.8884 -1.67596 17.6797 -2.09774 18.6401 -0.791927Z"
                          fill="#749BFF"
                        />
                      </g>
                      <g filter="url(#filter9_f_6186_74474)">
                        <path
                          d="M10.7557 5.45955C14.5954 1.89805 15.9132 -2.92402 13.6993 -5.31083C11.4854 -7.69765 6.57799 -6.74538 2.73837 -3.18387C-1.10124 0.377632 -2.41912 5.1997 -0.205187 7.58651C2.00875 9.97333 6.91612 9.02106 10.7557 5.45955Z"
                          fill="#FC413D"
                        />
                      </g>
                      <g filter="url(#filter10_f_6186_74474)">
                        <path
                          d="M2.8847 18.2518C5.16678 19.8851 7.78677 20.1333 8.73663 18.8062C9.68649 17.479 8.60652 15.0791 6.32444 13.4458C4.04237 11.8124 1.42237 11.5642 0.472513 12.8914C-0.477344 14.2185 0.60263 16.6184 2.8847 18.2518Z"
                          fill="#FFEE48"
                        />
                      </g>
                    </g>
                    <defs>
                      <filter
                        id="filter0_f_6186_74474"
                        x="-6.71946"
                        y="4.45898"
                        width="13.3139"
                        height="14.6511"
                        filterUnits="userSpaceOnUse"
                        colorInterpolationFilters="sRGB"
                      >
                        <feFlood floodOpacity={0} result="BackgroundImageFix" />
                        <feBlend
                          mode="normal"
                          in="SourceGraphic"
                          in2="BackgroundImageFix"
                          result="shape"
                        />
                        <feGaussianBlur
                          stdDeviation="0.83385"
                          result="effect1_foregroundBlur_6186_74474"
                        />
                      </filter>
                      <filter
                        id="filter1_f_6186_74474"
                        x="-5.08588"
                        y="-13.6475"
                        width="28.7714"
                        height="29.0492"
                        filterUnits="userSpaceOnUse"
                        colorInterpolationFilters="sRGB"
                      >
                        <feFlood floodOpacity={0} result="BackgroundImageFix" />
                        <feBlend
                          mode="normal"
                          in="SourceGraphic"
                          in2="BackgroundImageFix"
                          result="shape"
                        />
                        <feGaussianBlur
                          stdDeviation="4.03122"
                          result="effect1_foregroundBlur_6186_74474"
                        />
                      </filter>
                      <filter
                        id="filter2_f_6186_74474"
                        x="-7.04332"
                        y="4.04362"
                        width="26.9363"
                        height="30.8218"
                        filterUnits="userSpaceOnUse"
                        colorInterpolationFilters="sRGB"
                      >
                        <feFlood floodOpacity={0} result="BackgroundImageFix" />
                        <feBlend
                          mode="normal"
                          in="SourceGraphic"
                          in2="BackgroundImageFix"
                          result="shape"
                        />
                        <feGaussianBlur
                          stdDeviation="3.42693"
                          result="effect1_foregroundBlur_6186_74474"
                        />
                      </filter>
                      <filter
                        id="filter3_f_6186_74474"
                        x="-7.04332"
                        y="4.04362"
                        width="26.9363"
                        height="30.8218"
                        filterUnits="userSpaceOnUse"
                        colorInterpolationFilters="sRGB"
                      >
                        <feFlood floodOpacity={0} result="BackgroundImageFix" />
                        <feBlend
                          mode="normal"
                          in="SourceGraphic"
                          in2="BackgroundImageFix"
                          result="shape"
                        />
                        <feGaussianBlur
                          stdDeviation="3.42693"
                          result="effect1_foregroundBlur_6186_74474"
                        />
                      </filter>
                      <filter
                        id="filter4_f_6186_74474"
                        x="-6.72789"
                        y="5.24092"
                        width="27.03"
                        height="27.6311"
                        filterUnits="userSpaceOnUse"
                        colorInterpolationFilters="sRGB"
                      >
                        <feFlood floodOpacity={0} result="BackgroundImageFix" />
                        <feBlend
                          mode="normal"
                          in="SourceGraphic"
                          in2="BackgroundImageFix"
                          result="shape"
                        />
                        <feGaussianBlur
                          stdDeviation="3.42693"
                          result="effect1_foregroundBlur_6186_74474"
                        />
                      </filter>
                      <filter
                        id="filter5_f_6186_74474"
                        x="10.1138"
                        y="-3.91632"
                        width="25.4658"
                        height="25.0049"
                        filterUnits="userSpaceOnUse"
                        colorInterpolationFilters="sRGB"
                      >
                        <feFlood floodOpacity={0} result="BackgroundImageFix" />
                        <feBlend
                          mode="normal"
                          in="SourceGraphic"
                          in2="BackgroundImageFix"
                          result="shape"
                        />
                        <feGaussianBlur
                          stdDeviation="3.25659"
                          result="effect1_foregroundBlur_6186_74474"
                        />
                      </filter>
                      <filter
                        id="filter6_f_6186_74474"
                        x="-13.0796"
                        y="-5.5099"
                        width="26.4882"
                        height="26.6999"
                        filterUnits="userSpaceOnUse"
                        colorInterpolationFilters="sRGB"
                      >
                        <feFlood floodOpacity={0} result="BackgroundImageFix" />
                        <feBlend
                          mode="normal"
                          in="SourceGraphic"
                          in2="BackgroundImageFix"
                          result="shape"
                        />
                        <feGaussianBlur
                          stdDeviation="2.95141"
                          result="effect1_foregroundBlur_6186_74474"
                        />
                      </filter>
                      <filter
                        id="filter7_f_6186_74474"
                        x="2.74906"
                        y="-2.02234"
                        width="26.7402"
                        height="26.2868"
                        filterUnits="userSpaceOnUse"
                        colorInterpolationFilters="sRGB"
                      >
                        <feFlood floodOpacity={0} result="BackgroundImageFix" />
                        <feBlend
                          mode="normal"
                          in="SourceGraphic"
                          in2="BackgroundImageFix"
                          result="shape"
                        />
                        <feGaussianBlur
                          stdDeviation="2.63573"
                          result="effect1_foregroundBlur_6186_74474"
                        />
                      </filter>
                      <filter
                        id="filter8_f_6186_74474"
                        x="4.60627"
                        y="-6.2676"
                        width="19.0765"
                        height="17.5642"
                        filterUnits="userSpaceOnUse"
                        colorInterpolationFilters="sRGB"
                      >
                        <feFlood floodOpacity={0} result="BackgroundImageFix" />
                        <feBlend
                          mode="normal"
                          in="SourceGraphic"
                          in2="BackgroundImageFix"
                          result="shape"
                        />
                        <feGaussianBlur
                          stdDeviation="2.35848"
                          result="effect1_foregroundBlur_6186_74474"
                        />
                      </filter>
                      <filter
                        id="filter9_f_6186_74474"
                        x="-5.26335"
                        y="-10.6099"
                        width="24.0208"
                        height="23.4955"
                        filterUnits="userSpaceOnUse"
                        colorInterpolationFilters="sRGB"
                      >
                        <feFlood floodOpacity={0} result="BackgroundImageFix" />
                        <feBlend
                          mode="normal"
                          in="SourceGraphic"
                          in2="BackgroundImageFix"
                          result="shape"
                        />
                        <feGaussianBlur
                          stdDeviation="1.99203"
                          result="effect1_foregroundBlur_6186_74474"
                        />
                      </filter>
                      <filter
                        id="filter10_f_6186_74474"
                        x="-4.80302"
                        y="7.10711"
                        width="18.815"
                        height="17.4833"
                        filterUnits="userSpaceOnUse"
                        colorInterpolationFilters="sRGB"
                      >
                        <feFlood floodOpacity={0} result="BackgroundImageFix" />
                        <feBlend
                          mode="normal"
                          in="SourceGraphic"
                          in2="BackgroundImageFix"
                          result="shape"
                        />
                        <feGaussianBlur
                          stdDeviation="2.46547"
                          result="effect1_foregroundBlur_6186_74474"
                        />
                      </filter>
                      <linearGradient
                        id="paint0_linear_6186_74474"
                        x1="6.25389"
                        y1="14.72"
                        x2="17.6804"
                        y2="5.08636"
                        gradientUnits="userSpaceOnUse"
                      >
                        <stop stopColor="#4893FC" />
                        <stop offset="0.27" stopColor="#4893FC" />
                        <stop offset="0.776981" stopColor="#969DFF" />
                        <stop offset={1} stopColor="#BD99FE" />
                      </linearGradient>
                    </defs>
                  </svg>
                </div>

                <div>
                  <p className="font-medium text-gray-800 dark:text-white/90">
                    Gemini
                  </p>
                  <p className="text-sm text-gray-500 dark:text-gray-400">
                    {formatConfiguredKey(t("aiDashboard.apiToken.configuredKey"), 1)}
                  </p>
                </div>
              </div>
              {/* <!-- Right --> */}
              <div className="text-end">
                <div className="flex items-center justify-end gap-1">
                  <span className="size-[5px] rounded-full bg-purple-300"></span>
                  <span className="text-sm font-medium text-gray-700 dark:text-gray-400">
                    2M
                  </span>
                </div>
                <p className="text-xs text-gray-500 dark:text-gray-400">
                  {t("aiDashboard.apiToken.tokenUsed")}
                </p>
              </div>
            </li>
            <li className="flex items-center justify-between px-4 py-3">
              {/* <!-- Left --> */}
              <div className="flex items-center gap-3">
                <div className="flex size-10 items-center justify-center rounded-full border border-gray-200 dark:border-gray-800">
                  <svg
                    className="block dark:hidden"
                    xmlns="http://www.w3.org/2000/svg"
                    width="17"
                    height="18"
                    viewBox="0 0 17 18"
                    fill="none"
                  >
                    <path
                      d="M13.2569 5.79799L13.5668 18H16.049L16.3593 1.35603L13.2569 5.79799Z"
                      fill="#1D2939"
                    />
                    <path
                      d="M16.3593 0H12.5718L6.62844 8.51004L8.52218 11.2214L16.3593 0Z"
                      fill="#1D2939"
                    />
                    <path
                      d="M0 18H3.78747L5.68158 15.2887L3.78747 12.577L0 18Z"
                      fill="#1D2939"
                    />
                    <path
                      d="M0 5.79799L8.52218 18H12.3096L3.78747 5.79799H0Z"
                      fill="#1D2939"
                    />
                  </svg>
                  <svg
                    className="hidden dark:block"
                    xmlns="http://www.w3.org/2000/svg"
                    width="17"
                    height="18"
                    viewBox="0 0 17 18"
                    fill="none"
                  >
                    <path
                      d="M13.2569 5.79799L13.5668 18H16.049L16.3593 1.35603L13.2569 5.79799Z"
                      fill="white"
                      fillOpacity="0.9"
                    />
                    <path
                      d="M16.3593 0H12.5718L6.62844 8.51004L8.52218 11.2214L16.3593 0Z"
                      fill="white"
                      fillOpacity="0.9"
                    />
                    <path
                      d="M0 18H3.78747L5.68158 15.2887L3.78747 12.577L0 18Z"
                      fill="white"
                      fillOpacity="0.9"
                    />
                    <path
                      d="M0 5.79799L8.52218 18H12.3096L3.78747 5.79799H0Z"
                      fill="white"
                      fillOpacity="0.9"
                    />
                  </svg>
                </div>

                <div>
                  <p className="font-medium text-gray-800 dark:text-white/90">
                    xAI
                  </p>
                  <p className="text-sm text-gray-500 dark:text-gray-400">
                    {formatConfiguredKey(t("aiDashboard.apiToken.configuredKey"), 2)}
                  </p>
                </div>
              </div>
              {/* <!-- Right --> */}
              <div className="text-end">
                <div className="flex items-center justify-end gap-1">
                  <span className="bg-blue-light-300 size-[5px] rounded-full"></span>
                  <span className="text-sm font-medium text-gray-700 dark:text-gray-400">
                    4.5M
                  </span>
                </div>
                <p className="text-xs text-gray-500 dark:text-gray-400">
                  {t("aiDashboard.apiToken.tokenUsed")}
                </p>
              </div>
            </li>
          </ul>
          <a
            href="#"
            className="flex justify-center transition-all px-4 hover:text-gray-800 dark:hover:text-white/90 py-3 text-center text-sm font-medium text-gray-500 dark:text-gray-400"
          >
            {t("aiDashboard.apiToken.viewAllUsageDetails")}
          </a>
        </div>
      </div>
    </div>
  );
}
