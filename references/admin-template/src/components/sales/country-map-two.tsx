import VectorMap from "@/components/common/VectorMap";

export default function CountryMapTwo() {
  return (
    <VectorMap
      map="world"
      markerStyle={{
        initial: {
          fill: "#465FFF",
          fillOpacity: 1,
          strokeWidth: 0,
          r: 4,
        },
        hover: {
          fill: "#3538CD",
          fillOpacity: 1,
        },
      }}
      markersSelectable={true}
      markers={[
        {
          coords: [37.0902, -95.7129],
          name: "United States",
          style: { fill: "#465FFF", strokeWidth: 1, stroke: "white" },
        },
        {
          coords: [-14.235, -51.9253],
          name: "Brazil",
          style: { fill: "#465FFF", strokeWidth: 1, stroke: "white" },
        },
        {
          coords: [9.082, 8.6753],
          name: "Nigeria",
          style: { fill: "#465FFF", strokeWidth: 1, stroke: "white" },
        },
        {
          coords: [20.5937, 78.9629],
          name: "India",
          style: { fill: "#465FFF", strokeWidth: 1, stroke: "white" },
        },
        {
          coords: [-25.2744, 133.7751],
          name: "Australia",
          style: { fill: "#465FFF", strokeWidth: 1, stroke: "white" },
        },
      ]}
      selectedRegions={["US"]}
      zoomButtons={false}
      zoomOnScroll={false}
      zoomMax={12}
      zoomMin={1}
      zoomAnimate={true}
      zoomStep={1.5}
      regionStyle={{
        initial: {
          fill: "#9CB9FF",
          fillOpacity: 1,
          fontFamily: "Outfit",
          stroke: "transparent",
          strokeWidth: 1,
          strokeOpacity: 0,
        },
        hover: {
          fillOpacity: 1,
          cursor: "pointer",
          fill: "#8098F9",
          stroke: "none",
        },
        selected: {
          fill: "#465FFF",
        },
        selectedHover: {},
      }}
      regionLabelStyle={{
        initial: {
          fill: "#35373e",
          fontWeight: 500,
          fontSize: "13px",
          stroke: "none",
        },
        hover: {},
        selected: {},
        selectedHover: {},
      }}
    />
  );
}
