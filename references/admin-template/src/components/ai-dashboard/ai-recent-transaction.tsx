import { useState } from "react";
import { useTranslation } from "react-i18next";
import TableDropdown from "../common/TableDropdown";
import Badge from "../ui/badge/Badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHeader,
  TableRow,
} from "../ui/table";

interface Transaction {
  id: number;
  name: string;
  email: string;
  packageName: string;
  price: string;
  paidDate: string;
  status: "Active" | "Expired";
}

const tableData: Transaction[] = [
  {
    id: 1,
    name: "John Doe",
    email: "johndeo@gmail.com",
    packageName: "Starter - Monthly",
    price: "$20.00",
    paidDate: "28 Feb, 2029",
    status: "Active",
  },
  {
    id: 2,
    name: "kierra@gmail.com",
    email: "kierra@gmail.com",
    packageName: "Growth - Yearly",
    price: "$249.00",
    paidDate: "28 Jan, 2029",
    status: "Active",
  },
  {
    id: 3,
    name: "Emerson Workman",
    email: "emerson@gmail.com",
    packageName: "Premium - Monthly",
    price: "$199.00",
    paidDate: "5 Jan, 2029",
    status: "Expired",
  },
  {
    id: 4,
    name: "Chance Philips",
    email: "chance@gmail.com",
    packageName: "Growth - Yearly",
    price: "$249.00",
    paidDate: "12 Dec, 2028",
    status: "Active",
  },
  {
    id: 5,
    name: "Terry Geidt",
    email: "terry@gmail.com",
    packageName: "Starter - Monthly",
    price: "$20.00",
    paidDate: "25 Nov, 2028",
    status: "Expired",
  },
  {
    id: 6,
    name: "Maren Workman",
    email: "maren@gmail.com",
    packageName: "Premium - Monthly",
    price: "$199.00",
    paidDate: "5 Jan, 2029",
    status: "Active",
  },
  {
    id: 7,
    name: "Kian Philips",
    email: "kian@gmail.com",
    packageName: "Growth - Yearly",
    price: "$249.00",
    paidDate: "12 Dec, 2028",
    status: "Active",
  },
  {
    id: 8,
    name: "Terry Lipshutz",
    email: "terry@gmail.com",
    packageName: "Starter - Monthly",
    price: "$20.00",
    paidDate: "25 Nov, 2028",
    status: "Expired",
  },
  {
    id: 9,
    name: "John Doe",
    email: "johndeo@gmail.com",
    packageName: "Starter - Monthly",
    price: "$20.00",
    paidDate: "28 Feb, 2029",
    status: "Active",
  },
  {
    id: 10,
    name: "kierra@gmail.com",
    email: "kierra@gmail.com",
    packageName: "Growth - Yearly",
    price: "$249.00",
    paidDate: "28 Jan, 2029",
    status: "Active",
  },
  {
    id: 11,
    name: "Emerson Workman",
    email: "emerson@gmail.com",
    packageName: "Premium - Monthly",
    price: "$199.00",
    paidDate: "5 Jan, 2029",
    status: "Expired",
  },
  {
    id: 12,
    name: "Chance Philips",
    email: "chance@gmail.com",
    packageName: "Growth - Yearly",
    price: "$249.00",
    paidDate: "12 Dec, 2028",
    status: "Active",
  },
  {
    id: 13,
    name: "Terry Geidt",
    email: "terry@gmail.com",
    packageName: "Starter - Monthly",
    price: "$20.00",
    paidDate: "25 Nov, 2028",
    status: "Expired",
  },
];

export default function AiRecentTransaction() {
  const { t } = useTranslation();
  const [currentPage, setCurrentPage] = useState(1);
  const [searchTerm, setSearchTerm] = useState("");
  const itemsPerPage = 5;

  const handleViewMore = () => {
    //logic will be there
  };

  const handleDelete = () => {
    //logic will be there
  };

  const getPackageName = (packageName: string) => {
    switch (packageName) {
      case "Starter - Monthly":
        return t("aiDashboard.recentTransactions.packages.starterMonthly");
      case "Growth - Yearly":
        return t("aiDashboard.recentTransactions.packages.growthYearly");
      case "Premium - Monthly":
        return t("aiDashboard.recentTransactions.packages.premiumMonthly");
      default:
        return packageName;
    }
  };

  // Filter data based on search term
  const filteredData = tableData.filter(
    (item) =>
      item.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      item.email.toLowerCase().includes(searchTerm.toLowerCase()) ||
      item.packageName.toLowerCase().includes(searchTerm.toLowerCase()),
  );

  // Pagination logic
  const totalPages = Math.ceil(filteredData.length / itemsPerPage);
  const startIndex = (currentPage - 1) * itemsPerPage;
  const paginatedData = filteredData.slice(
    startIndex,
    startIndex + itemsPerPage,
  );

  const handlePageChange = (page: number) => {
    if (page >= 1 && page <= totalPages) {
      setCurrentPage(page);
    }
  };

  const renderPageNumbers = () => {
    const pages = [];
    const maxVisiblePages = 5;

    if (totalPages <= maxVisiblePages) {
      for (let i = 1; i <= totalPages; i++) {
        pages.push(i);
      }
    } else {
      if (currentPage <= 3) {
        pages.push(1, 2, 3, 4, "...", totalPages);
      } else if (currentPage >= totalPages - 2) {
        pages.push(
          1,
          "...",
          totalPages - 3,
          totalPages - 2,
          totalPages - 1,
          totalPages,
        );
      } else {
        pages.push(
          1,
          "...",
          currentPage - 1,
          currentPage,
          currentPage + 1,
          "...",
          totalPages,
        );
      }
    }
    return pages;
  };
  return (
    <div className="rounded-2xl border border-gray-200 bg-white dark:border-gray-800 dark:bg-white/3">
      <div className="flex flex-col gap-2 px-6 py-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h3 className="text-lg font-semibold text-gray-800 dark:text-white/90">
            {t("aiDashboard.recentTransactions.title")}
          </h3>
        </div>

        <div className="flex gap-3 sm:items-center">
          <form className="flex-1" onSubmit={(e) => e.preventDefault()}>
            <div className="relative">
              <span className="pointer-events-none absolute start-4 top-1/2 -translate-y-1/2">
                <svg
                  className="fill-gray-500 dark:fill-gray-400"
                  width="20"
                  height="20"
                  viewBox="0 0 20 20"
                  fill="none"
                  xmlns="http://www.w3.org/2000/svg"
                >
                  <path
                    fillRule="evenodd"
                    clipRule="evenodd"
                    d="M3.04199 9.37381C3.04199 5.87712 5.87735 3.04218 9.37533 3.04218C12.8733 3.04218 15.7087 5.87712 15.7087 9.37381C15.7087 12.8705 12.8733 15.7055 9.37533 15.7055C5.87735 15.7055 3.04199 12.8705 3.04199 9.37381ZM9.37533 1.54218C5.04926 1.54218 1.54199 5.04835 1.54199 9.37381C1.54199 13.6993 5.04926 17.2055 9.37533 17.2055C11.2676 17.2055 13.0032 16.5346 14.3572 15.4178L17.1773 18.2381C17.4702 18.531 17.945 18.5311 18.2379 18.2382C18.5308 17.9453 18.5309 17.4704 18.238 17.1775L15.4182 14.3575C16.5367 13.0035 17.2087 11.2671 17.2087 9.37381C17.2087 5.04835 13.7014 1.54218 9.37533 1.54218Z"
                    fill=""
                  />
                </svg>
              </span>
              <input
                type="text"
                placeholder={t(
                  "aiDashboard.recentTransactions.searchPlaceholder",
                )}
                value={searchTerm}
                onChange={(e) => {
                  setSearchTerm(e.target.value);
                  setCurrentPage(1);
                }}
                className="dark:bg-dark-900 h-10 w-full rounded-lg border border-gray-300 bg-transparent py-2.5 ps-[42px] pe-4 text-sm text-gray-800 shadow-theme-xs placeholder:text-gray-400 focus:border-brand-300 focus:ring-3 focus:ring-brand-500/10 focus:outline-hidden xl:w-[300px] dark:border-gray-700 dark:bg-gray-900 dark:text-white/90 dark:placeholder:text-white/30 dark:focus:border-brand-800"
              />
            </div>
          </form>
          <div>
            <button className="inline-flex h-10 items-center gap-2 rounded-lg border border-gray-300 bg-white px-4 py-2.5 text-theme-sm font-medium text-gray-700 shadow-theme-xs hover:bg-gray-50 hover:text-gray-800 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-400 dark:hover:bg-white/3 dark:hover:text-gray-200">
              <svg
                className="fill-white stroke-current dark:fill-gray-800"
                width="20"
                height="20"
                viewBox="0 0 20 20"
                fill="none"
                xmlns="http://www.w3.org/2000/svg"
              >
                <path
                  d="M2.29004 5.90393H17.7067"
                  stroke=""
                  strokeWidth="1.5"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
                <path
                  d="M17.7075 14.0961H2.29085"
                  stroke=""
                  strokeWidth="1.5"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
                <path
                  d="M12.0826 3.33331C13.5024 3.33331 14.6534 4.48431 14.6534 5.90414C14.6534 7.32398 13.5024 8.47498 12.0826 8.47498C10.6627 8.47498 9.51172 7.32398 9.51172 5.90415C9.51172 4.48432 10.6627 3.33331 12.0826 3.33331Z"
                  fill=""
                  stroke=""
                  strokeWidth="1.5"
                />
                <path
                  d="M7.91745 11.525C6.49762 11.525 5.34662 12.676 5.34662 14.0959C5.34661 15.5157 6.49762 16.6667 7.91745 16.6667C9.33728 16.6667 10.4883 15.5157 10.4883 14.0959C10.4883 12.676 9.33728 11.525 7.91745 11.525Z"
                  fill=""
                  stroke=""
                  strokeWidth="1.5"
                />
              </svg>
              {t("aiDashboard.recentTransactions.filter")}
            </button>
          </div>
        </div>
      </div>

      <div className="custom-scrollbar max-w-full overflow-x-auto overflow-y-visible">
        <Table className="min-w-full">
          <TableHeader className="border-y border-gray-100 bg-gray-50 py-3 dark:border-gray-800 dark:bg-gray-900">
            <TableRow>
              <TableCell
                isHeader
                className="px-6 py-3 font-normal whitespace-nowrap sm:pe-6"
              >
                <div className="flex items-center">
                  <p className="text-theme-sm text-gray-500 dark:text-gray-400">
                    {t("aiDashboard.recentTransactions.table.paidBy")}
                  </p>
                </div>
              </TableCell>
              <TableCell
                isHeader
                className="px-6 py-3 font-normal whitespace-nowrap sm:px-6"
              >
                <div className="flex items-center">
                  <p className="text-theme-sm text-gray-500 dark:text-gray-400">
                    {t("aiDashboard.recentTransactions.table.packageName")}
                  </p>
                </div>
              </TableCell>
              <TableCell
                isHeader
                className="px-6 py-3 font-normal whitespace-nowrap sm:px-6"
              >
                <div className="flex items-center">
                  <p className="text-theme-sm text-gray-500 dark:text-gray-400">
                    {t("aiDashboard.recentTransactions.table.price")}
                  </p>
                </div>
              </TableCell>
              <TableCell
                isHeader
                className="px-6 py-3 font-normal whitespace-nowrap sm:px-6"
              >
                <div className="flex items-center">
                  <p className="text-theme-sm text-gray-500 dark:text-gray-400">
                    {t("aiDashboard.recentTransactions.table.paidDate")}
                  </p>
                </div>
              </TableCell>
              <TableCell
                isHeader
                className="px-6 py-3 font-normal whitespace-nowrap sm:px-6"
              >
                <div className="flex items-center">
                  <p className="text-theme-sm text-gray-500 dark:text-gray-400">
                    {t("aiDashboard.recentTransactions.table.status")}
                  </p>
                </div>
              </TableCell>
              <TableCell
                isHeader
                className="px-6 py-3 font-normal whitespace-nowrap sm:px-6"
              >
                <p className="text-theme-sm text-gray-500 dark:text-gray-400">
                  {t("aiDashboard.recentTransactions.table.actions")}
                </p>
              </TableCell>
            </TableRow>
          </TableHeader>
          <TableBody className="divide-y divide-gray-100 dark:divide-gray-800">
            {paginatedData.length > 0 ? (
              paginatedData.map((row) => (
                <TableRow key={row.id}>
                  <TableCell className="px-6 py-4 whitespace-nowrap sm:pe-5">
                    <div className="flex items-center gap-3">
                      <div>
                        <p className="block text-theme-sm font-medium text-gray-700 dark:text-gray-400">
                          {row.name}
                        </p>
                        <p className="text-sm text-gray-500 dark:text-gray-400">
                          {row.email}
                        </p>
                      </div>
                    </div>
                  </TableCell>
                  <TableCell className="px-5 py-4 whitespace-nowrap sm:px-6">
                    <p className="text-theme-sm text-gray-700 dark:text-gray-400">
                      {getPackageName(row.packageName)}
                    </p>
                  </TableCell>
                  <TableCell className="px-5 py-4 whitespace-nowrap sm:px-6">
                    <p className="text-theme-sm text-gray-700 dark:text-gray-400">
                      {row.price}
                    </p>
                  </TableCell>
                  <TableCell className="px-5 py-4 whitespace-nowrap sm:px-6">
                    <p className="text-theme-sm text-gray-700 dark:text-gray-400">
                      {row.paidDate}
                    </p>
                  </TableCell>
                  <TableCell className="px-5 py-4 whitespace-nowrap sm:px-6">
                    <Badge
                      color={row.status === "Active" ? "success" : "error"}
                      size="sm"
                    >
                      {row.status === "Active"
                        ? t("aiDashboard.recentTransactions.statuses.active")
                        : t("aiDashboard.recentTransactions.statuses.expired")}
                    </Badge>
                  </TableCell>
                  <TableCell className="px-5 py-4 whitespace-nowrap sm:px-6">
                    <div className="flex items-center justify-center">
                      <TableDropdown
                        dropdownButton={
                          <button className="text-gray-500 dark:text-gray-400">
                            <svg
                              className="fill-current"
                              width="24"
                              height="24"
                              viewBox="0 0 24 24"
                              fill="none"
                              xmlns="http://www.w3.org/2000/svg"
                            >
                              <path
                                fillRule="evenodd"
                                clipRule="evenodd"
                                d="M5.99902 10.245C6.96552 10.245 7.74902 11.0285 7.74902 11.995V12.005C7.74902 12.9715 6.96552 13.755 5.99902 13.755C5.03253 13.755 4.24902 12.9715 4.24902 12.005V11.995C4.24902 11.0285 5.03253 10.245 5.99902 10.245ZM17.999 10.245C18.9655 10.245 19.749 11.0285 19.749 11.995V12.005C19.749 12.9715 18.9655 13.755 17.999 13.755C17.0325 13.755 16.249 12.9715 16.249 12.005V11.995C16.249 11.0285 17.0325 10.245 17.999 10.245ZM13.749 11.995C13.749 11.0285 12.9655 10.245 11.999 10.245C11.0325 10.245 10.249 11.0285 10.249 11.995V12.005C10.249 12.9715 11.0325 13.755 11.999 13.755C12.9655 13.755 13.749 12.9715 13.749 12.005V11.995Z"
                                fill=""
                              />
                            </svg>
                          </button>
                        }
                        dropdownContent={
                          <>
                            <button
                              onClick={handleViewMore}
                              className="flex w-full rounded-lg px-3 py-2 text-start text-xs font-medium text-gray-500 hover:bg-gray-100 hover:text-gray-700 dark:text-gray-400 dark:hover:bg-white/5 dark:hover:text-gray-300"
                            >
                              {t("common.viewMore")}
                            </button>
                            <button
                              onClick={handleDelete}
                              className="flex w-full rounded-lg px-3 py-2 text-start text-xs font-medium text-gray-500 hover:bg-gray-100 hover:text-gray-700 dark:text-gray-400 dark:hover:bg-white/5 dark:hover:text-gray-300"
                            >
                              {t("common.delete")}
                            </button>
                          </>
                        }
                      />
                    </div>
                  </TableCell>
                </TableRow>
              ))
            ) : (
              <TableRow>
                <TableCell className="px-6 py-10 text-center text-gray-500 dark:text-gray-400">
                  {t("aiDashboard.recentTransactions.noResults")}
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>

      <div className="border-t border-gray-200 px-6 py-4 dark:border-gray-800">
        <div className="flex items-center justify-between">
          <button
            onClick={() => handlePageChange(currentPage - 1)}
            disabled={currentPage === 1}
            className="flex items-center gap-2 rounded-lg border border-gray-300 bg-white px-2 py-2 text-theme-sm font-medium text-gray-700 shadow-theme-xs hover:bg-gray-50 hover:text-gray-800 disabled:opacity-50 sm:px-3.5 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-400 dark:hover:bg-white/3 dark:hover:text-gray-200"
          >
            <svg
              className="fill-current rtl:rotate-180"
              width="20"
              height="20"
              viewBox="0 0 20 20"
              fill="none"
              xmlns="http://www.w3.org/2000/svg"
            >
              <path
                fillRule="evenodd"
                clipRule="evenodd"
                d="M2.58301 9.99868C2.58272 10.1909 2.65588 10.3833 2.80249 10.53L7.79915 15.5301C8.09194 15.8231 8.56682 15.8233 8.85981 15.5305C9.15281 15.2377 9.15297 14.7629 8.86018 14.4699L5.14009 10.7472L16.6675 10.7472C17.0817 10.7472 17.4175 10.4114 17.4175 9.99715C17.4175 9.58294 17.0817 9.24715 16.6675 9.24715L5.14554 9.24715L8.86017 5.53016C9.15297 5.23717 9.15282 4.7623 8.85983 4.4695C8.56684 4.1767 8.09197 4.17685 7.79917 4.46984L2.84167 9.43049C2.68321 9.568 2.58301 9.77087 2.58301 9.99715C2.58301 9.99766 2.58301 9.99817 2.58301 9.99868Z"
                fill=""
              />
            </svg>

            <span className="hidden sm:inline">
              {" "}
              {t("aiDashboard.recentTransactions.pagination.previous")}{" "}
            </span>
          </button>

          <span className="block text-sm font-medium text-gray-700 sm:hidden dark:text-gray-400">
            {t("aiDashboard.recentTransactions.pagination.pageOf", {
              current: currentPage,
              total: totalPages,
            })}
          </span>

          <ul className="hidden items-center gap-0.5 sm:flex">
            {renderPageNumbers().map((page, index) => (
              <li key={index}>
                {page === "..." ? (
                  <span className="flex h-10 w-10 items-center justify-center rounded-lg text-theme-sm font-medium text-gray-700 dark:text-gray-400">
                    ...
                  </span>
                ) : (
                  <button
                    onClick={() => handlePageChange(page as number)}
                    className={`flex h-10 w-10 items-center justify-center rounded-lg text-sm font-medium ${
                      currentPage === page
                        ? "bg-brand-500 text-white"
                        : "text-gray-700 hover:bg-brand-500/[0.08] hover:text-brand-500 dark:text-gray-400 dark:hover:text-brand-500"
                    }`}
                  >
                    {page}
                  </button>
                )}
              </li>
            ))}
          </ul>

          <button
            onClick={() => handlePageChange(currentPage + 1)}
            disabled={currentPage === totalPages}
            className="flex items-center gap-2 rounded-lg border border-gray-300 bg-white px-2 py-2 text-theme-sm font-medium text-gray-700 shadow-theme-xs hover:bg-gray-50 hover:text-gray-800 disabled:opacity-50 sm:px-3.5 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-400 dark:hover:bg-white/3 dark:hover:text-gray-200"
          >
            <span className="hidden sm:inline">
              {" "}
              {t("aiDashboard.recentTransactions.pagination.next")}{" "}
            </span>

            <svg
              className="fill-current rtl:rotate-180"
              width="20"
              height="20"
              viewBox="0 0 20 20"
              fill="none"
              xmlns="http://www.w3.org/2000/svg"
            >
              <path
                fillRule="evenodd"
                clipRule="evenodd"
                d="M17.4175 9.9986C17.4178 10.1909 17.3446 10.3832 17.198 10.53L12.2013 15.5301C11.9085 15.8231 11.4337 15.8233 11.1407 15.5305C10.8477 15.2377 10.8475 14.7629 11.1403 14.4699L14.8604 10.7472L3.33301 10.7472C2.91879 10.7472 2.58301 10.4114 2.58301 9.99715C2.58301 9.58294 2.91879 9.24715 3.33301 9.24715L14.8549 9.24715L11.1403 5.53016C10.8475 5.23717 10.8477 4.7623 11.1407 4.4695C11.4336 4.1767 11.9085 4.17685 12.2013 4.46984L17.1588 9.43049C17.3173 9.568 17.4175 9.77087 17.4175 9.99715C17.4175 9.99763 17.4175 9.99812 17.4175 9.9986Z"
                fill=""
              />
            </svg>
          </button>
        </div>
      </div>
    </div>
  );
}
