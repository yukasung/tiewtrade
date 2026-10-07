import VectorMap from "@/components/common/VectorMap";
import { useEffect, useRef } from "react";

export default function VectorMapTwo() {
  const mapRef = useRef<any>(null);
  useEffect(() => {
    const style = document.createElement("style");
    style.id = "map-traffic-styles";
    style.innerHTML = `
      #mapTrafficAnalytics path[data-code="US"], #mapTrafficAnalytics .jvm-region[data-code="US"] { fill: #3538CD !important; }
      #mapTrafficAnalytics path[data-code="CA"], #mapTrafficAnalytics .jvm-region[data-code="CA"] { fill: #8098F9 !important; }
      #mapTrafficAnalytics path[data-code="CN"], #mapTrafficAnalytics .jvm-region[data-code="CN"] { fill: #8098F9 !important; }
      #mapTrafficAnalytics path[data-code="FR"], #mapTrafficAnalytics .jvm-region[data-code="FR"] { fill: #9CB9FF !important; }
      #mapTrafficAnalytics path[data-code="BR"], #mapTrafficAnalytics .jvm-region[data-code="BR"] { fill: #9CB9FF !important; }
      #mapTrafficAnalytics path[data-code="RU"], #mapTrafficAnalytics .jvm-region[data-code="RU"] { fill: #9CB9FF !important; }
      #mapTrafficAnalytics path[data-code="AU"], #mapTrafficAnalytics .jvm-region[data-code="AU"] { fill: #ADC6FF !important; }
    `;
    document.head.appendChild(style);
    return () => {
      const existing = document.getElementById("map-traffic-styles");
      if (existing) document.head.removeChild(existing);
    };
  }, []);

  return (
    <div className="rounded-2xl border border-gray-200 bg-white p-5 sm:p-6 dark:border-gray-800 dark:bg-white/3">
      <div className="mb-5">
        <h3 className="text-lg font-semibold text-gray-800 dark:text-white/90">
          Country Traffic Analytics
        </h3>
        <p className="mt-1 text-theme-sm text-gray-500 dark:text-gray-400">
          Visualize traffic volume and engagement by region
        </p>
      </div>

      <div className="relative overflow-hidden rounded-2xl border border-gray-200 bg-gray-50 dark:border-gray-800 dark:bg-gray-900">
        <div
          id="mapTrafficAnalytics"
          className="map-btn w-full"
          style={{ height: "274px" }}
        >
          <VectorMap
            map="world"
            zoomButtons={false}
            zoomOnScroll={false}
            zoomAnimate={true}
            zoomStep={1.5}
            zoomMax={12}
            zoomMin={1}
            regionStyle={{
              initial: {
                fill: "#C5D8FF",
                fillOpacity: 1,
                stroke: "white",
                strokeWidth: 0.5,
                strokeOpacity: 1,
              },
              hover: {
                fillOpacity: 0.8,
                fill: "#465FFF",
                cursor: "pointer",
              },
              selected: {
                fill: "#3538CD",
              },
              selectedHover: {},
            }}
            onRegionTipShow={() => {}}
            mapRef={mapRef}
            style={{ width: "100%", height: "100%" }}
          />
        </div>

        <div className="absolute right-3 bottom-3 z-10">
          <div className="flex flex-col overflow-hidden rounded-lg border border-gray-200 bg-white dark:border-gray-800 dark:bg-gray-900">
            <button
              onClick={() => {
                const map = mapRef.current;
                if (map)
                  map.setScale(
                    map.scale * 1.5,
                    map.width / 2,
                    map.height / 2,
                    false,
                    true,
                  );
              }}
              className="flex h-9 w-9 items-center justify-center border-b border-gray-200 text-gray-500 hover:bg-gray-100 hover:text-gray-700 dark:border-gray-800 dark:text-gray-400 dark:hover:bg-white/5 dark:hover:text-white"
              aria-label="Zoom in"
            >
              <svg
                width="16"
                height="16"
                viewBox="0 0 16 16"
                fill="none"
                xmlns="http://www.w3.org/2000/svg"
              >
                <path
                  d="M8 3.33334V12.6667M3.33334 8H12.6667"
                  stroke="currentColor"
                  strokeWidth="1.5"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
            </button>
            <button
              onClick={() => {
                const map = mapRef.current;
                if (map)
                  map.setScale(
                    map.scale / 1.5,
                    map.width / 2,
                    map.height / 2,
                    false,
                    true,
                  );
              }}
              className="flex h-9 w-9 items-center justify-center text-gray-500 hover:bg-gray-100 hover:text-gray-700 dark:text-gray-400 dark:hover:bg-white/5 dark:hover:text-white"
              aria-label="Zoom out"
            >
              <svg
                width="16"
                height="16"
                viewBox="0 0 16 16"
                fill="none"
                xmlns="http://www.w3.org/2000/svg"
              >
                <path
                  d="M3.33334 8H12.6667"
                  stroke="currentColor"
                  strokeWidth="1.5"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
