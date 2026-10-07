import VectorMap from "@/components/common/VectorMap";
import { useRef } from "react";
import "./us-aea-en";

export default function VectorMapThree() {
  const mapRef = useRef<any>(null);
  const markers = [
    { name: "Denver", coords: [39.73, -104.99] as [number, number] },
    { name: "Seattle", coords: [47.6, -122.33] as [number, number] },
    { name: "Miami", coords: [25.76, -80.19] as [number, number] },
    { name: "Minneapolis", coords: [44.97, -93.26] as [number, number] },
    { name: "Washington D.C.", coords: [38.9, -77.03] as [number, number] },
    { name: "San Francisco", coords: [37.77, -122.41] as [number, number] },
    { name: "Phoenix", coords: [33.44, -112.07] as [number, number] },
    { name: "San Antonio", coords: [29.42, -98.49] as [number, number] },
  ];

  return (
    <div className="rounded-2xl border border-gray-200 bg-white p-5 sm:p-6 dark:border-gray-800 dark:bg-white/3">
      <div className="mb-5">
        <h3 className="text-lg font-semibold text-gray-800 dark:text-white/90">
          US Customer Heatmap
        </h3>
        <p className="mt-1 text-theme-sm text-gray-500 dark:text-gray-400">
          Analyze customer density and regional performance
        </p>
      </div>

      <div className="relative overflow-hidden rounded-2xl border border-gray-200 bg-gray-50 dark:border-gray-800 dark:bg-gray-900">
        <div
          id="mapCustomerPinPoint"
          className="map-btn w-full"
          style={{ height: "274px" }}
        >
          <VectorMap
            map="us_aea_en"
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
                strokeWidth: 2,
                strokeOpacity: 1,
              },
              hover: {
                fillOpacity: 0.8,
                fill: "#465FFF",
                cursor: "pointer",
              },
              selected: {
                fill: "#465FFF",
              },
              selectedHover: {},
            }}
            markers={markers}
            markerStyle={{
              initial: {
                fill: "#465FFF",
                stroke: "white",
                strokeWidth: 1,
                r: 5,
              },
              hover: {
                fill: "#3538CD",
              },
              selected: {},
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
