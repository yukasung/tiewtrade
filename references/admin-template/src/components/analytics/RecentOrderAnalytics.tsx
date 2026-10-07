import { useTranslation } from "react-i18next";
import { SliderHorizontalIcon } from "../../icons";
import Button from "../ui/button/Button";
import {
  Table,
  TableBody,
  TableCell,
  TableHeader,
  TableRow,
} from "../ui/table";

// Define the TypeScript interface for the table rows
interface Product {
  id: number; // Unique identifier for each product
  name: string; // Product name
  categoryKey: "uiKits" | "templates" | "saas"; // Category key of the product
  country: string; // Path to the country flag image
  crKey: "crDashboard"; // Conversion rate label key
  value: string;
}

// Define the table data using the interface
const tableData: Product[] = [
  {
    id: 1,
    name: "TailGrids",
    categoryKey: "uiKits",
    country: "/images/country/country-01.svg",
    crKey: "crDashboard",
    value: "12,499",
  },
  {
    id: 2,
    name: "GrayGrids",
    categoryKey: "templates",
    country: "/images/country/country-02.svg",
    crKey: "crDashboard",
    value: "5498",
  },
  {
    id: 3,
    name: "Uideck",
    categoryKey: "templates",
    country: "/images/country/country-03.svg",
    crKey: "crDashboard",
    value: "4621",
  },
  {
    id: 4,
    name: "FormBold",
    categoryKey: "saas",
    country: "/images/country/country-04.svg",
    crKey: "crDashboard",
    value: "13843",
  },
  {
    id: 5,
    name: "NextAdmin",
    categoryKey: "templates",
    country: "/images/country/country-05.svg",
    crKey: "crDashboard",
    value: "7523",
  },
  {
    id: 6,
    name: "Form Builder",
    categoryKey: "templates",
    country: "/images/country/country-06.svg",
    crKey: "crDashboard",
    value: "1,377",
  },
  {
    id: 7,
    name: "AyroUI",
    categoryKey: "templates",
    country: "/images/country/country-07.svg",
    crKey: "crDashboard",
    value: "599,00",
  },
];

export default function RecentOrderAnalytics() {
  const { t } = useTranslation();

  return (
    <div className="overflow-hidden rounded-2xl border border-gray-200 bg-white dark:border-white/[0.05] dark:bg-white/3">
      <div className="px-4 pt-4 sm:px-6">
        <div className="mb-4 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h3 className="text-lg font-semibold text-gray-800 dark:text-white/90">
              {t("analytics.recentOrders.title")}
            </h3>
          </div>

          <div className="flex items-center gap-3">
            <Button
              size="sm"
              variant="outline"
              className="flex items-center gap-2"
            >
              <SliderHorizontalIcon className="size-5" />
              {t("common.filter")}
            </Button>
            <Button size="sm" variant="outline">
              {t("common.seeAll")}
            </Button>
          </div>
        </div>
      </div>
      <div className="max-w-full">
        <div className="overflow-x-auto">
          <Table>
            {/* Table Header */}
            <TableHeader className="border-y border-gray-100 dark:border-white/[0.05]">
              <TableRow>
                <TableCell
                  isHeader
                  className="px-4 py-3 text-start text-theme-xs font-medium text-gray-500 sm:px-6 dark:text-gray-400"
                >
                  {t("analytics.recentOrders.products")}
                </TableCell>
                <TableCell
                  isHeader
                  className="px-4 py-3 text-start text-theme-xs font-medium text-gray-500 sm:px-6 dark:text-gray-400"
                >
                  {t("analytics.recentOrders.category")}
                </TableCell>
                <TableCell
                  isHeader
                  className="px-4 py-3 text-start text-theme-xs font-medium text-gray-500 sm:px-6 dark:text-gray-400"
                >
                  {t("analytics.recentOrders.country")}
                </TableCell>
                <TableCell
                  isHeader
                  className="px-4 py-3 text-start text-theme-xs font-medium text-gray-500 sm:px-6 dark:text-gray-400"
                >
                  {t("analytics.recentOrders.cr")}
                </TableCell>
                <TableCell
                  isHeader
                  className="px-4 py-3 text-start text-theme-xs font-medium text-gray-500 sm:px-6 dark:text-gray-400"
                >
                  {t("analytics.recentOrders.value")}
                </TableCell>
              </TableRow>
            </TableHeader>

            {/* Table Body */}
            <TableBody className="divide-y divide-gray-100 dark:divide-white/[0.05]">
              {tableData.map((product) => (
                <TableRow key={product.id}>
                  <TableCell className="px-4 py-3 text-start text-theme-sm font-medium text-gray-800 sm:px-6 dark:text-white/90">
                    {product.name}
                  </TableCell>
                  <TableCell className="px-4 py-3 text-start text-theme-sm text-gray-500 sm:px-6 dark:text-gray-400">
                    {t(
                      `analytics.recentOrders.categories.${product.categoryKey}`,
                    )}
                  </TableCell>
                  <TableCell className="px-4 py-3 text-start text-theme-sm text-gray-500 sm:px-6 dark:text-gray-400">
                    <div className="h-5 w-5 overflow-hidden rounded-full">
                      <img
                        src={product.country}
                        className="h-5 w-5 rounded-full"
                        alt="country"
                      />
                    </div>
                  </TableCell>
                  <TableCell className="px-4 py-3 text-start text-theme-sm text-gray-500 sm:px-6 dark:text-gray-400">
                    {t(`analytics.recentOrders.${product.crKey}`)}
                  </TableCell>
                  <TableCell className="px-4 text-start text-theme-sm text-success-600 sm:px-6">
                    ${product.value}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      </div>
    </div>
  );
}
