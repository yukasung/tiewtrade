import PageBreadcrumb from "../../components/common/PageBreadCrumb";
import ComponentCard from "../../components/common/ComponentCard";
import PieChartOne from "../../components/charts/pie/PieChartOne";
import PieChartTwo from "../../components/charts/pie/PieChartTwo";
import PageMeta from "../../components/common/PageMeta";
import PieChartThree from "../../components/charts/pie/PieChartThree";
import PieChartFour from "../../components/charts/pie/PieChartFour";
import PieChartFive from "../../components/charts/pie/PieChartFive";

export default function PieChart() {
  return (
    <div>
      <PageMeta
        title="React.js Chart Dashboard | TailAdmin - React.js Admin Dashboard Template"
        description="This is React.js Chart Dashboard page for TailAdmin - React.js Tailwind CSS Admin Dashboard Template"
      />
      <PageBreadcrumb pageTitle="Pie Chart" />
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <ComponentCard title="Donut Pie Chart 1">
          <PieChartOne />
        </ComponentCard>
        <ComponentCard title="Donut Pie Chart 2">
          <PieChartTwo />
        </ComponentCard>
        <ComponentCard title="Donut Pie Chart 3">
          <PieChartThree />
        </ComponentCard>
        <ComponentCard title="Pie Chart 4">
          <PieChartFour />
        </ComponentCard>
        <ComponentCard title="Pie Chart 5">
          <PieChartFive />
        </ComponentCard>
      </div>
    </div>
  );
}
