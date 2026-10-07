import * as maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { useRef } from "react";
import type { MapRef } from "react-map-gl/maplibre";
import Map from "react-map-gl/maplibre";

// MapLibre v6: configure web worker URL once at module scope before map creation
if (typeof window !== "undefined") {
  maplibregl.setWorkerUrl("/maplibre/maplibre-gl-worker.mjs");
}

export default function MapOne() {
  const mapRef = useRef<MapRef>(null);

  const handleZoomIn = () => {
    mapRef.current?.zoomIn();
  };

  const handleZoomOut = () => {
    mapRef.current?.zoomOut();
  };

  return (
    <div className="rounded-2xl border border-gray-200 bg-white p-5 sm:p-6 dark:border-gray-800 dark:bg-white/3">
      <div className="mb-5 flex items-start justify-between">
        <div>
          <h3 className="text-lg font-semibold text-gray-800 dark:text-white/90">
            Map View
          </h3>
          <p className="mt-1 text-theme-sm text-gray-500 dark:text-gray-400">
            Clear view of locations at a glance
          </p>
        </div>
      </div>

      <div className="relative z-0 overflow-hidden rounded-2xl border border-gray-200 dark:border-gray-800">
        {/* Visually hidden description for screen readers */}
        <p id="mapLocationView3Desc" className="sr-only">
          Interactive map showing the Washington D.C. metro area. Use arrow keys
          to pan and plus/minus keys to zoom.
        </p>
        <div
          id="mapLocationView3"
          className="h-75 w-full"
          role="application"
          aria-label="Interactive location map"
          aria-describedby="mapLocationView3Desc"
          tabIndex={0}
        >
          <Map
            ref={mapRef}
            mapLib={maplibregl}
            initialViewState={{
              longitude: -77.0369,
              latitude: 38.9072,
              zoom: 8.5,
            }}
            mapStyle="https://tiles.openfreemap.org/styles/bright"
            scrollZoom={false}
            attributionControl={false}
            style={{ width: "100%", height: "100%" }}
          />
        </div>

        {/* Zoom Controls */}
        <div className="absolute inset-e-3 top-3 z-999">
          <div className="flex flex-col overflow-hidden rounded-lg border border-gray-200 bg-white dark:border-gray-800 dark:bg-gray-900">
            <button
              id="mapLocationZoomIn3"
              type="button"
              onClick={handleZoomIn}
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
              id="mapLocationZoomOut3"
              type="button"
              onClick={handleZoomOut}
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
