import PageMeta from "../../components/common/PageMeta";
import CashflowOverview from "../../components/finance/CashflowOverview";
import FinanceStats from "../../components/finance/FinanceStats";
import FinanceTransactionTable from "../../components/finance/FinanceTransactionTable";
import MyCards from "../../components/finance/MyCards";
import QuickSend from "../../components/finance/QuickSend";
import SpendingWidget from "../../components/finance/SpendingWidget";
import TotalBalanceOverview from "../../components/finance/TotalBalanceOverview";

export default function FinanceDashboard() {
  return (
    <>
      <PageMeta
        title="React.js Finance Dashboard | TailAdmin - React.js Admin Dashboard Template"
        description="This is React.js Finance Dashboard page for TailAdmin - React.js Tailwind CSS Admin Dashboard Template"
      />
      <div className="space-y-5">
        <div className="grid grid-cols-1 gap-5 xl:grid-cols-12">
          <div className="xl:col-span-6 2xl:col-span-5">
            <TotalBalanceOverview />
          </div>
          <div className="xl:col-span-6 2xl:col-span-7">
            <FinanceStats />
          </div>
        </div>
        <div className="grid grid-cols-1 gap-5 xl:grid-cols-12">
          <div className="col-span-12 space-y-5 xl:col-span-8">
            <CashflowOverview />
            <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
              <SpendingWidget />
              <QuickSend />
            </div>
          </div>
          <div className="col-span-12 xl:col-span-4">
            <MyCards />
          </div>
        </div>
        <FinanceTransactionTable />
      </div>
    </>
  );
}
