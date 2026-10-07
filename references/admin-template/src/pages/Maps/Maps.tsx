import PageMeta from "@/components/common/PageMeta";
import MapOne from "@/components/maps/others/MapOne";
import MapThree from "@/components/maps/others/MapThree";
import MapTwo from "@/components/maps/others/MapTwo";

export default function Maps() {
  return (
    <div>
      <PageMeta
        title="React.js Blank Page | TailAdmin - React.js Admin Dashboard Template"
        description="This is React.js Blank Page for TailAdmin - React.js Tailwind CSS Admin Dashboard Template"
      />
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <MapOne />
        <MapTwo />
        <MapThree />
      </div>
    </div>
  );
}
