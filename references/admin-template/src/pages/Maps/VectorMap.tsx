import PageMeta from "../../components/common/PageMeta";
import VectorMapOne from "../../components/maps/vector-map/VectorMapOne";
import VectorMapThree from "../../components/maps/vector-map/VectorMapThree";
import VectorMapTwo from "../../components/maps/vector-map/VectorMapTwo";

export default function VectorMap() {
  return (
    <div>
      <PageMeta
        title="React.js Blank Page | TailAdmin - React.js Admin Dashboard Template"
        description="This is React.js Blank Page for TailAdmin - React.js Tailwind CSS Admin Dashboard Template"
      />
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <VectorMapOne />
        <VectorMapTwo />
        <VectorMapThree />
      </div>
    </div>
  );
}
