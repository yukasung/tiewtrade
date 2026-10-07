import { Link } from "react-router";
import AddIntegrationModal from "@/components/integration/AddIntegrationModal";
import { cn } from "@/utils";

interface BreadcrumbProps {
  pageTitle: string;
  className?: string;
}

const IntegrationBreadcrumb: React.FC<BreadcrumbProps> = ({
  pageTitle,
  className,
}) => {
  return (
    <div
      className={cn(
        "mb-6 flex flex-col justify-between gap-3 sm:flex-row sm:items-center",
        className
      )}
    >
      <h2 className="text-start text-xl font-semibold text-gray-800 dark:text-white/90">
        {pageTitle}
      </h2>
      <nav className="flex flex-col gap-6 sm:flex-row sm:items-center">
        <ol className="flex items-center gap-1.5">
          <li>
            <Link
              className="inline-flex items-center gap-1.5 text-sm text-gray-500 dark:text-gray-400"
              to="/"
            >
              Home
              <svg
                className="stroke-current rtl:rotate-180"
                width="17"
                height="16"
                viewBox="0 0 17 16"
                fill="none"
                xmlns="http://www.w3.org/2000/svg"
              >
                <path
                  d="M6.0765 12.667L10.2432 8.50033L6.0765 4.33366"
                  stroke=""
                  strokeWidth="1.2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
            </Link>
          </li>
          <li className="text-sm text-gray-800 dark:text-white/90">
            {pageTitle}
          </li>
        </ol>
        <AddIntegrationModal />
      </nav>
    </div>
  );
};

export default IntegrationBreadcrumb;

