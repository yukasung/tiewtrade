import PageBreadcrumb from "../../components/common/PageBreadCrumb";
import ComponentCard from "../../components/common/ComponentCard";
import PageMeta from "../../components/common/PageMeta";
import RadialOne from "../../components/charts/radial/RadialOne";
import RadialTwo from "../../components/charts/radial/RadialTwo";
import RadialThree from "../../components/charts/radial/RadialThree";
import RadialFour from "../../components/charts/radial/RadialFour";

export default function RadialChart() {
  return (
    <>
      <PageMeta
        title="React.js Chart Dashboard | TailAdmin - React.js Admin Dashboard Template"
        description="This is React.js Chart Dashboard page for TailAdmin - React.js Tailwind CSS Admin Dashboard Template"
      />
      <PageBreadcrumb pageTitle="Radial Chart" />
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <ComponentCard title="Radial Chart 1">
          <RadialOne />
        </ComponentCard>
        <ComponentCard title="Radial Chart 2">
          <RadialTwo />
        </ComponentCard>
        <ComponentCard title="Radial Chart 3">
          <RadialThree />
        </ComponentCard>
        <ComponentCard title="Radial Chart 4">
          <RadialFour />
        </ComponentCard>
      </div>
    </>
  );
}
