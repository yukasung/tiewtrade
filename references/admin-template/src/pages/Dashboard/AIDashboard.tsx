import AiRecentTransaction from "@/components/ai-dashboard/ai-recent-transaction";
import AiStats from "@/components/ai-dashboard/ai-stats";
import ApiToken from "@/components/ai-dashboard/api-token";
import ProjectAnalytics from "@/components/ai-dashboard/project-analytics";
import UserAnalytics from "@/components/ai-dashboard/user-analytics";
import UserRevenueAndStatistics from "@/components/ai-dashboard/user-revenue-and-statistics";
import PageMeta from "@/components/common/PageMeta";

export default function AIDashboard() {
  return (
    <>
      <PageMeta
        title="React.js AI Dashboard | TailAdmin - React.js Admin Dashboard Template"
        description="This is React.js AI Dashboard page for TailAdmin - React.js Tailwind CSS Admin Dashboard Template"
      />
      <div className="space-y-6">
        <AiStats />
        <div className="grid grid-cols-1 gap-6 xl:grid-cols-12">
          <div className="xl:col-span-8">
            <UserRevenueAndStatistics />
          </div>
          <div className="xl:col-span-4">
            <ApiToken />
          </div>
        </div>
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
          <UserAnalytics />
          <ProjectAnalytics />
        </div>

        <AiRecentTransaction />
      </div>
    </>
  );
}
