import BarChartFive from "@/components/charts/bar/BarChartFive";
import BarChartFour from "@/components/charts/bar/BarChartFour";
import BarChartOne from "@/components/charts/bar/BarChartOne";
import BarChartSix from "@/components/charts/bar/BarChartSix";
import BarChartThree from "@/components/charts/bar/BarChartThree";
import BarChartTwo from "@/components/charts/bar/BarChartTwo";
import ComponentCard from "@/components/common/ComponentCard";
import PageBreadcrumb from "@/components/common/PageBreadCrumb";
import PageMeta from "@/components/common/PageMeta";

export default function BarChart() {
  return (
    <div>
      <PageMeta
        title="React.js Chart Dashboard | TailAdmin - React.js Admin Dashboard Template"
        description="This is React.js Chart Dashboard page for TailAdmin - React.js Tailwind CSS Admin Dashboard Template"
      />
      <PageBreadcrumb pageTitle="Bar Chart" />
      <div className="space-y-6">
        <ComponentCard title="Bar Chart 1">
          <BarChartOne />
        </ComponentCard>
        <ComponentCard title="Bar Chart 2">
          <BarChartTwo />
        </ComponentCard>
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
          <ComponentCard title="Bar Chart 3">
            <BarChartThree />
          </ComponentCard>
          <ComponentCard title="Horizontal Bar Chart">
            <BarChartFour />
          </ComponentCard>
          <ComponentCard title="Bar Chart 5">
            <BarChartFive />
          </ComponentCard>
          <ComponentCard title="Bar Chart 6">
            <BarChartSix />
          </ComponentCard>
        </div>
      </div>
    </div>
  );
}
