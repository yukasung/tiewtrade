import { useTranslation } from "react-i18next";

export default function FinanceStats() {
  const { t } = useTranslation();

  return (
    <div className="rounded-[18px] border border-gray-200 bg-gray-100 p-1.5 dark:border-gray-800 dark:bg-white/3">
      <div className="grid grid-cols-1 gap-1.5 sm:grid-cols-2">
        <div className="flex flex-col justify-between rounded-xl bg-white p-6 dark:bg-gray-900">
          <div>
            <div className="mb-1.5 flex items-center justify-between">
              <p className="text-base text-gray-500 dark:text-gray-400">
                {t("finance.stats.totalBalance")}
              </p>
              <span className="bg-brand-500/10 inline-flex size-9 items-center justify-center rounded-lg">
                <svg
                  width="24"
                  height="24"
                  viewBox="0 0 24 24"
                  fill="none"
                  xmlns="http://www.w3.org/2000/svg"
                >
                  <path
                    d="M4 8H18.5C19.3284 8 20 8.67157 20 9.5V18.5C20 19.3284 19.3284 20 18.5 20H5.5C4.67157 20 4 19.3284 4 18.5V8ZM4 8V5.5C4 4.67157 4.67157 4 5.5 4H16C16.8284 4 17.5 4.67157 17.5 5.5V8M20 12H16.75C15.9216 12 15.25 12.6716 15.25 13.5V14.5C15.25 15.3284 15.9216 16 16.75 16H20"
                    stroke="#465FFF"
                    strokeWidth="1.5"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                </svg>
              </span>
            </div>
            <h2 className="text-3xl font-medium text-gray-700 dark:text-white/90">
              $24,830
            </h2>
          </div>
          <p className="flex items-center gap-1.5 text-sm font-normal text-gray-500 dark:text-gray-400">
            <span className="text-success-600 flex items-center gap-1 font-medium">
              <svg
                width="16"
                height="16"
                viewBox="0 0 16 16"
                fill="none"
                xmlns="http://www.w3.org/2000/svg"
              >
                <path
                  d="M7.9974 2.66602L7.9974 13.3336M4 6.66334L7.99987 2.66602L12 6.66334"
                  stroke="#039855"
                  strokeWidth="1.5"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
              3.2%
            </span>
            {t("finance.stats.thanLastMonth")}
          </p>
        </div>
        <div className="rounded-xl bg-white p-6 dark:bg-gray-900">
          <div className="mb-9.5">
            <div className="mb-1.5 flex items-center justify-between">
              <p className="text-base text-gray-500 dark:text-gray-400">
                {t("finance.stats.monthlyIncome")}
              </p>
              <span className="bg-success-500/10 inline-flex size-9 items-center justify-center rounded-lg">
                <svg
                  width="24"
                  height="24"
                  viewBox="0 0 24 24"
                  fill="none"
                  xmlns="http://www.w3.org/2000/svg"
                >
                  <path
                    d="M20.0005 20H5.5C4.67157 20 4 19.3284 4 18.5V4M4 15.4191L9.19963 10.2195L13.1523 14.1722L18.7431 8.58135M18.7431 8.58135L18.7471 12.1162M18.7431 8.58135L15.2115 8.58067"
                    stroke="#12B76A"
                    strokeWidth="1.5"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                </svg>
              </span>
            </div>
            <h2 className="text-3xl font-medium text-gray-700 dark:text-white/90">
              $5,200
            </h2>
          </div>
          <p className="flex items-center gap-1.5 text-sm font-normal text-gray-500 dark:text-gray-400">
            <span className="flex items-center gap-1 font-medium text-red-600">
              <svg
                width="16"
                height="16"
                viewBox="0 0 16 16"
                fill="none"
                xmlns="http://www.w3.org/2000/svg"
              >
                <path
                  d="M7.9974 13.3338L7.9974 2.66626M4 9.33644L7.99987 13.3338L12 9.33644"
                  stroke="#D92D20"
                  strokeWidth="1.5"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
              3.2%
            </span>
            {t("finance.stats.thanLastMonth")}
          </p>
        </div>
        <div className="rounded-xl bg-white p-6 dark:bg-gray-900">
          <div className="mb-9.5">
            <div className="mb-1.5 flex items-center justify-between">
              <p className="text-base text-gray-500 dark:text-gray-400">
                {t("finance.stats.totalSpent")}
              </p>
              <span className="inline-flex size-9 items-center justify-center rounded-lg bg-orange-500/10">
                <svg
                  width="24"
                  height="24"
                  viewBox="0 0 24 24"
                  fill="none"
                  xmlns="http://www.w3.org/2000/svg"
                >
                  <path
                    d="M2.75 10.5V17.25C2.75 18.0784 3.42157 18.75 4.25 18.75H9.30078M2.75 10.5V9M2.75 10.5H12.082C12.082 10.5 13.7908 9.00694 16.6263 9M2.75 9V6.75C2.75 5.92157 3.42157 5.25 4.25 5.25H19.75C20.5784 5.25 21.25 5.92157 21.25 6.75V9M2.75 9H16.6263M21.25 9V10.5625C21.25 10.5625 19.532 9.00701 16.666 9M21.25 9H16.666M16.6263 9C16.6395 8.99997 16.6528 8.99997 16.666 9M16.6263 9H16.666M18.375 14.4768C18.375 13.7519 17.7873 13.1642 17.0624 13.1642H16.375C15.5466 13.1642 14.875 13.8358 14.875 14.6642V14.9293C14.875 15.5546 15.2628 16.1142 15.8483 16.3338L17.4017 16.9164C17.9872 17.1359 18.375 17.6956 18.375 18.3209V18.5859C18.375 19.4144 17.7034 20.0859 16.875 20.0859H16.1876C15.4627 20.0859 14.875 19.4983 14.875 18.7733M16.625 20.0859V21.25M16.625 12V13.1642"
                    stroke="#FB6514"
                    strokeWidth="1.5"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                </svg>
              </span>
            </div>
            <h2 className="text-3xl font-medium text-gray-700 dark:text-white/90">
              $3,831
            </h2>
          </div>
          <p className="flex items-center gap-1.5 text-sm font-normal text-gray-500 dark:text-gray-400">
            <span className="text-success-600 flex items-center gap-1 font-medium">
              <svg
                width="16"
                height="16"
                viewBox="0 0 16 16"
                fill="none"
                xmlns="http://www.w3.org/2000/svg"
              >
                <path
                  d="M7.9974 2.66602L7.9974 13.3336M4 6.66334L7.99987 2.66602L12 6.66334"
                  stroke="#039855"
                  strokeWidth="1.5"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
              295
            </span>
            {t("finance.stats.thanLastMonth")}
          </p>
        </div>
        <div className="rounded-xl bg-white p-6 dark:bg-gray-900">
          <div className="mb-9.5">
            <div className="mb-1.5 flex items-center justify-between">
              <p className="text-base text-gray-500 dark:text-gray-400">
                {t("finance.stats.savingRate")}
              </p>
              <span className="inline-flex size-9 items-center justify-center rounded-lg bg-pink-500/10">
                <svg
                  width="24"
                  height="24"
                  viewBox="0 0 24 24"
                  fill="none"
                  xmlns="http://www.w3.org/2000/svg"
                >
                  <path
                    d="M11.999 15.4605H11.5616C10.8367 15.4605 10.249 14.8728 10.249 14.1479M11.999 15.4605H12.249C13.0775 15.4605 13.749 14.7889 13.749 13.9605V13.6954C13.749 13.0701 13.3612 12.5105 12.7757 12.2909L11.2223 11.7083C10.6369 11.4888 10.249 10.9291 10.249 10.3038V10.0388C10.249 9.21034 10.9206 8.53876 11.749 8.53876H11.999M11.999 15.4605V16.6245M11.999 8.53876H12.4364C13.1614 8.53876 13.749 9.12643 13.749 9.85136M11.999 8.53876V7.37452M19.9994 7.76672V12.7605C19.9994 14.782 18.9814 16.6676 17.2914 17.7767L12.8227 20.7094C12.323 21.0373 11.6763 21.0373 11.1767 20.7094L6.70797 17.7767C5.01792 16.6676 4 14.782 4 12.7605V7.76672C4 7.035 4.52576 6.40446 5.23056 6.20778C6.65684 5.80977 9.09916 4.94592 11.3415 3.27064C11.7304 2.9801 12.269 2.9801 12.6578 3.27064C14.9002 4.94592 17.3425 5.80977 18.7688 6.20778C19.4736 6.40446 19.9994 7.035 19.9994 7.76672Z"
                    stroke="#EE46BC"
                    strokeWidth="1.5"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                </svg>
              </span>
            </div>
            <h2 className="text-3xl font-medium text-gray-700 dark:text-white/90">
              26.1%
            </h2>
          </div>
          <p className="flex items-center gap-2.5 text-sm font-normal text-gray-500 dark:text-gray-400">
            <span>
              <svg
                width="24"
                height="24"
                viewBox="0 0 24 24"
                fill="none"
                xmlns="http://www.w3.org/2000/svg"
              >
                <circle
                  className="stroke-gray-300 dark:stroke-gray-700"
                  cx="12"
                  cy="12"
                  r="10.75"
                  stroke="currentColor"
                  strokeWidth="2.5"
                />
                <mask id="path-2-inside-1_6585_25873" fill="white">
                  <path d="M12 0C14.3225 2.76958e-08 16.5951 0.673978 18.5422 1.94017C20.4892 3.20636 22.0269 5.01036 22.9688 7.13331C23.9108 9.25625 24.2164 11.6069 23.8486 13.9001C23.4808 16.1934 22.4555 18.3306 20.897 20.0525L19.0444 18.3758C20.2784 17.0124 21.0902 15.3202 21.3814 13.5045C21.6725 11.6888 21.4306 9.82759 20.6848 8.1467C19.939 6.46581 18.7215 5.03747 17.1799 4.03493C15.6383 3.0324 13.8389 2.49876 12 2.49876V0Z" />
                </mask>
                <path
                  d="M12 0C14.3225 2.76958e-08 16.5951 0.673978 18.5422 1.94017C20.4892 3.20636 22.0269 5.01036 22.9688 7.13331C23.9108 9.25625 24.2164 11.6069 23.8486 13.9001C23.4808 16.1934 22.4555 18.3306 20.897 20.0525L19.0444 18.3758C20.2784 17.0124 21.0902 15.3202 21.3814 13.5045C21.6725 11.6888 21.4306 9.82759 20.6848 8.1467C19.939 6.46581 18.7215 5.03747 17.1799 4.03493C15.6383 3.0324 13.8389 2.49876 12 2.49876V0Z"
                  stroke="#465FFF"
                  strokeWidth="4"
                  mask="url(#path-2-inside-1_6585_25873)"
                />
              </svg>
            </span>
            {t("finance.stats.goalProgress")}
          </p>
        </div>
      </div>
    </div>
  );
}
