import VectorMap from "@/components/common/VectorMap";

export default function VectorMapOne() {
  const markers = [
    {
      name: "United States",
      coords: [37.2580397, -104.657039] as [number, number],
    },
    { name: "India", coords: [20.7504374, 73.7276105] as [number, number] },
    { name: "United Kingdom", coords: [53.613, -11.6368] as [number, number] },
    {
      name: "Australia",
      coords: [-25.0304388, 115.2092761] as [number, number],
    },
  ];

  return (
    <div className="rounded-2xl border border-gray-200 bg-white p-5 sm:p-6 dark:border-gray-800 dark:bg-white/3">
      <div className="mb-5">
        <h3 className="text-lg font-semibold text-gray-800 dark:text-white/90">
          Global User Distribution
        </h3>
        <p className="mt-1 text-theme-sm text-gray-500 dark:text-gray-400">
          Track active users and customer locations worldwide
        </p>
      </div>

      <div className="overflow-hidden rounded-2xl border border-gray-200 bg-gray-50 dark:border-gray-800 dark:bg-gray-900">
        <div className="map-btn relative w-full" style={{ height: "274px" }}>
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
                fontFamily: "Outfit",
                fill: "#D9D9D9",
                stroke: "none",
                strokeWidth: 0,
                strokeOpacity: 0,
              },
              hover: {
                fillOpacity: 0.7,
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
                strokeWidth: 1,
                fill: "#465FFF",
                fillOpacity: 1,
                r: 4,
              },
              hover: {
                fill: "#3538CD",
                fillOpacity: 1,
              },
              selected: {},
              selectedHover: {},
            }}
            onRegionTipShow={() => {}}
            style={{ width: "100%", height: "100%" }}
          />
        </div>
      </div>
    </div>
  );
}
