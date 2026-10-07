import PageMeta from "@/components/common/PageMeta";
import SalesChannel from "@/components/sales/sales-channel";
import SalesChannelCountry from "@/components/sales/sales-channel-country";
import UserRetentionTable from "@/components/sales/sales-country-table";
import SalesStats from "@/components/sales/sales-stats";
import TopProductTable from "@/components/sales/top-product";
import UserRevenueAndStats from "@/components/sales/user-revenue-and-stats-chart";

export default function SalesDashboard() {
  return (
    <>
      <PageMeta
        title="React.js Sales Dashboard | TailAdmin - React.js Admin Dashboard Template"
        description="This is React.js Sales Dashboard page for TailAdmin - React.js Tailwind CSS Admin Dashboard Template"
      />

      <div className="grid grid-cols-12 gap-4 md:gap-6">
        <div className="col-span-12">
          <SalesStats />
        </div>

        <div className="col-span-12">
          <UserRevenueAndStats />
        </div>

        <div className="col-span-12">
          <div className="grid grid-cols-1 gap-5 lg:grid-cols-2 xl:grid-cols-3">
            <UserRetentionTable />
            <SalesChannel />
            <SalesChannelCountry />
          </div>
        </div>

        <div className="col-span-12">
          <TopProductTable />
        </div>
      </div>
    </>
  );
}
