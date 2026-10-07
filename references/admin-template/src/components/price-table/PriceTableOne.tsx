import { CheckLineIcon } from "@/icons";
import { cn } from "@/utils";
import { useState } from "react";

const starterPack = [
  "5 website",
  "500 MB Storage",
  "Unlimited Sub-Domain",
  "3 Custom Domain",
  "Free SSL Certificate",
  "Unlimited Traffic",
];
const mediumPack = [
  "10 website",
  "1 GB Storage",
  "Unlimited Sub-Domain",
  "5 Custom Domain",
  "Free SSL Certificate",
  "Unlimited Traffic",
];
const largePack = [
  "15 website",
  "10 GB Storage",
  "Unlimited Sub-Domain",
  "10 Custom Domain",
  "Free SSL Certificate",
  "Unlimited Traffic",
];

export default function PriceTableOne() {
  const [isMonthly, setIsMonthly] = useState(true);
  return (
    <div>
      <div className="mx-auto w-full max-w-[385px]">
        <h2 className="mb-7 text-center text-title-sm font-bold text-gray-800 dark:text-white/90">
          Flexible Plans Tailored to Fit Your Unique Needs!
        </h2>
      </div>
      <div>
        <div className="mb-10 text-center">
          <div className="relative z-1 mx-auto inline-flex rounded-full bg-gray-200 p-1 dark:bg-gray-800">
            <span
              className={cn(
                "absolute start-1 top-1/2 -z-1 flex h-11 w-[120px] -translate-y-1/2 rounded-full bg-white shadow-theme-xs duration-200 ease-linear dark:bg-white/10",
                isMonthly
                  ? "translate-x-0"
                  : "translate-x-full rtl:-translate-x-full",
              )}
            ></span>
            <button
              onClick={() => setIsMonthly(true)}
              className={cn(
                "flex h-11 w-[120px] items-center justify-center text-base font-medium",
                isMonthly
                  ? "text-gray-800 dark:text-white/90"
                  : "text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-white/70",
              )}
            >
              Monthly
            </button>
            <button
              onClick={() => setIsMonthly(false)}
              className={cn(
                "flex h-11 w-[120px] items-center justify-center text-base font-medium",
                !isMonthly
                  ? "text-gray-800 dark:text-white/90"
                  : "text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-white/80",
              )}
            >
              Annually
            </button>
          </div>
        </div>

        <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 xl:grid-cols-3 xl:gap-6">
          {/* <!-- Pricing item --> */}
          <div className="rounded-2xl border border-gray-200 bg-white p-6 dark:border-gray-800 dark:bg-white/3">
            <span className="mb-3 block text-theme-xl font-semibold text-gray-800 dark:text-white/90">
              Starter
            </span>

            <div className="mb-1 flex items-center justify-between">
              <div className="flex items-end">
                <h2 className="text-title-md font-bold text-gray-800 dark:text-white/90">
                  ${isMonthly ? "5.00" : "40.00"}
                </h2>

                <span className="mb-1 inline-block text-sm text-gray-500 dark:text-gray-400">
                  /month
                </span>
              </div>
              <span className="text-theme-xl font-semibold text-gray-400 line-through">
                ${isMonthly ? "12.00" : "150.00"}
              </span>
            </div>

            <p className="text-sm text-gray-500 dark:text-gray-400">
              For solo designers & freelancers
            </p>

            <div className="my-6 h-px w-full bg-gray-200 dark:bg-gray-800"></div>

            <ul className="mb-8 space-y-3">
              {starterPack.map((item, index) => (
                <li
                  key={index}
                  className="flex items-center gap-3 text-sm text-gray-500 dark:text-gray-400"
                >
                  <CheckLineIcon className="text-success-500" />
                  {item}
                </li>
              ))}
            </ul>

            <button className="flex w-full items-center justify-center rounded-lg bg-gray-800 p-3.5 text-sm font-medium text-white shadow-theme-xs transition-colors hover:bg-brand-500 dark:bg-white/10 dark:hover:bg-brand-600">
              Choose Starter
            </button>
          </div>

          {/* <!-- Pricing item --> */}
          <div className="rounded-2xl border border-gray-800 bg-gray-800 p-6 dark:border-white/10 dark:bg-white/10">
            <span className="mb-3 block text-theme-xl font-semibold text-white">
              Medium
            </span>

            <div className="mb-1 flex items-center justify-between">
              <div className="flex items-end">
                <h2 className="text-title-md font-bold text-white">
                  ${isMonthly ? "10.99" : "100.00"}
                </h2>

                <span className="mb-1 inline-block text-sm text-white/70">
                  /month{" "}
                </span>
              </div>

              <span className="text-theme-xl font-semibold text-gray-300 line-through">
                ${isMonthly ? "30.00" : "250.00"}
              </span>
            </div>

            <p className="text-sm text-white/70">
              For working on commercial projects
            </p>

            <div className="my-6 h-px w-full bg-white/20"></div>

            <div className="mb-8 space-y-3">
              {mediumPack.map((item, index) => (
                <li
                  key={index}
                  className="flex items-center gap-3 text-sm text-white/80"
                >
                  <CheckLineIcon className="text-success-500" />
                  {item}
                </li>
              ))}
            </div>
            <button className="flex w-full items-center justify-center rounded-lg bg-brand-500 p-3.5 text-sm font-medium text-white shadow-theme-xs transition-colors hover:bg-brand-600 dark:hover:bg-brand-600">
              Choose Starter
            </button>
          </div>

          {/* <!-- Pricing item --> */}
          <div className="rounded-2xl border border-gray-200 bg-white p-6 dark:border-gray-800 dark:bg-white/3">
            <span className="mb-3 block text-theme-xl font-semibold text-gray-800 dark:text-white/90">
              Large
            </span>

            <div className="mb-1 flex items-center justify-between">
              <div className="flex items-end">
                <h2 className="text-title-md font-bold text-gray-800 dark:text-white/90">
                  ${isMonthly ? "15.00" : "190.00"}
                </h2>
                <span className="mb-1 inline-block text-sm text-gray-500 dark:text-gray-400">
                  /month
                </span>
              </div>
              <span className="text-theme-xl font-semibold text-gray-400 line-through">
                ${isMonthly ? "59.00" : "350.00"}
              </span>
            </div>

            <p className="text-sm text-gray-500 dark:text-gray-400">
              For teams larger than 5 members
            </p>

            <div className="my-6 h-px w-full bg-gray-200 dark:bg-gray-800"></div>

            <ul className="mb-8 space-y-3">
              {largePack.map((item, index) => (
                <li
                  key={index}
                  className="flex items-center gap-3 text-sm text-gray-500 dark:text-gray-400"
                >
                  <CheckLineIcon className="text-success-500" />
                  {item}
                </li>
              ))}
            </ul>
            <button className="flex w-full items-center justify-center rounded-lg bg-gray-800 p-3.5 text-sm font-medium text-white shadow-theme-xs transition-colors hover:bg-brand-500 dark:bg-white/10 dark:hover:bg-brand-600">
              Choose Starter
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
