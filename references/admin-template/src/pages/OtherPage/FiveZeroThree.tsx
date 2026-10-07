import GridShape from "@/components/common/GridShape";
import PageMeta from "@/components/common/PageMeta";
import { cn } from "@/utils";
import { Link } from "react-router";

interface FiveZeroThreeProps {
  className?: string;
}

export default function FiveZeroThree({ className }: FiveZeroThreeProps) {
  return (
    <>
      <PageMeta
        title="React.js 503 Page | TailAdmin - React.js Admin Dashboard Template"
        description="This is React.js 503 Page  for TailAdmin - React.js Tailwind CSS Admin Dashboard Template"
      />
      <div
        className={cn(
          "relative z-1 flex min-h-screen flex-col items-center justify-center overflow-hidden p-6",
          className,
        )}
      >
        <GridShape />

        <div className="mx-auto w-full max-w-[242px] text-center sm:max-w-[492px]">
          <h1 className="mb-8 text-title-md font-bold text-gray-800 xl:text-title-2xl dark:text-white/90">
            ERROR
          </h1>

          <img src="/images/error/503.svg" alt="503" className="dark:hidden" />
          <img
            src="/images/error/503-dark.svg"
            alt="503"
            className="hidden dark:block"
          />

          <p className="mt-10 mb-6 text-base text-gray-700 sm:text-lg dark:text-gray-400">
            We can’t seem to find the page you are looking for!
          </p>

          <Link
            to="/"
            className="inline-flex items-center justify-center rounded-lg border border-gray-300 bg-white px-5 py-3.5 text-sm font-medium text-gray-700 shadow-theme-xs hover:bg-gray-50 hover:text-gray-800 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-400 dark:hover:bg-white/3 dark:hover:text-gray-200"
          >
            Back to Home Page
          </Link>
        </div>

        {/* <!-- Footer --> */}
        <p className="absolute start-1/2 bottom-6 -translate-x-1/2 text-center text-sm text-gray-500 rtl:translate-x-1/2 dark:text-gray-400">
          &copy; {new Date().getFullYear()} - TailAdmin
        </p>
      </div>
    </>
  );
}
