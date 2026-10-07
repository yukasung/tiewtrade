import Checkbox from "@/components/form/input/Checkbox";
import AvatarText from "@/components/ui/avatar/AvatarText";
import Badge from "@/components/ui/badge/Badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { SliderHorizontalIcon, TrashBinIcon } from "@/icons";
import { useState } from "react";
import { useTranslation } from "react-i18next";

type ProductKey =
  | "softwareLicense"
  | "cloudHosting"
  | "webDomain"
  | "sslCertificate"
  | "premiumSupport";

type StatusType = "complete" | "pending" | "cancel";

// Interface for the table row data
interface TableRowData {
  id: string; // Unique identifier for the row
  user: {
    initials: string; // Initials for the avatar
    name: string; // User's full name
    email: string; // User's email address
  };
  avatarColor: "brand" | "blue" | "green" | "red" | "yellow" | "gray"; // Color variant for the avatar
  product: {
    nameKey: ProductKey; // Product name translation key
    price: string; // Product price
    purchaseDate: string; // Date of purchase
  };
  status: {
    type: StatusType; // Size of the badge
  };
  actions: {
    delete: boolean; // Indicates a delete action is available
  };
}

const tableRowData: TableRowData[] = [
  {
    id: "DE124321",
    user: {
      initials: "AB",
      name: "John Doe",
      email: "johndoe@gmail.com",
    },
    avatarColor: "brand",
    product: {
      nameKey: "softwareLicense",
      price: "$18,50.34",
      purchaseDate: "2024-06-15",
    },
    status: {
      type: "complete",
    },
    actions: {
      delete: true,
    },
  },
  {
    id: "DE124322",
    user: {
      initials: "CD",
      name: "Jane Smith",
      email: "janesmith@gmail.com",
    },
    avatarColor: "brand",
    product: {
      nameKey: "cloudHosting",
      price: "$12,99.00",
      purchaseDate: "2024-06-18",
    },
    status: {
      type: "pending",
    },
    actions: {
      delete: true,
    },
  },
  {
    id: "DE124323",
    user: {
      initials: "EF",
      name: "Michael Brown",
      email: "michaelbrown@gmail.com",
    },
    avatarColor: "brand",
    product: {
      nameKey: "webDomain",
      price: "$9,50.00",
      purchaseDate: "2024-06-20",
    },
    status: {
      type: "cancel",
    },
    actions: {
      delete: true,
    },
  },
  {
    id: "DE124324",
    user: {
      initials: "GH",
      name: "Alice Johnson",
      email: "alicejohnson@gmail.com",
    },
    avatarColor: "brand",
    product: {
      nameKey: "sslCertificate",
      price: "$2,30.45",
      purchaseDate: "2024-06-25",
    },
    status: {
      type: "pending",
    },
    actions: {
      delete: true,
    },
  },
  {
    id: "DE124325",
    user: {
      initials: "IJ",
      name: "Robert Lee",
      email: "robertlee@gmail.com",
    },
    avatarColor: "brand",
    product: {
      nameKey: "premiumSupport",
      price: "$15,20.00",
      purchaseDate: "2024-06-30",
    },
    status: {
      type: "complete",
    },
    actions: {
      delete: true,
    },
  },
];

export default function CrmRecentOrderTable() {
  const { t } = useTranslation();
  const [selectedRows, setSelectedRows] = useState<string[]>([]);
  const [selectAll, setSelectAll] = useState<boolean>(false);

  const handleSelectAll = () => {
    setSelectAll(!selectAll);
    if (!selectAll) {
      setSelectedRows(tableRowData.map((row) => row.id));
    } else {
      setSelectedRows([]);
    }
  };

  const handleRowSelect = (id: string) => {
    setSelectedRows((prevSelected) =>
      prevSelected.includes(id)
        ? prevSelected.filter((rowId) => rowId !== id)
        : [...prevSelected, id],
    );
  };
  return (
    <div className="overflow-hidden rounded-2xl border border-gray-200 bg-white pt-4 dark:border-gray-800 dark:bg-white/3">
      <div className="mb-4 flex flex-col gap-4 px-6 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h3 className="text-lg font-semibold text-gray-800 dark:text-white/90">
            {t("crm.recentOrders.title")}
          </h3>
        </div>
        <div className="flex items-center gap-3">
          <button className="inline-flex items-center gap-2 rounded-lg border border-gray-300 bg-white px-4 py-2.5 text-theme-sm font-medium text-gray-700 shadow-theme-xs hover:bg-gray-50 hover:text-gray-800 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-400 dark:hover:bg-white/3 dark:hover:text-gray-200">
            <SliderHorizontalIcon className="size-5" />
            {t("common.filter")}
          </button>
          <button className="inline-flex items-center gap-2 rounded-lg border border-gray-300 bg-white px-4 py-2.5 text-theme-sm font-medium text-gray-700 shadow-theme-xs hover:bg-gray-50 hover:text-gray-800 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-400 dark:hover:bg-white/3 dark:hover:text-gray-200">
            {t("common.seeAll")}
          </button>
        </div>
      </div>

      <div className="custom-scrollbar max-w-full overflow-x-auto">
        <Table>
          <TableHeader className="border-y border-t border-gray-100 bg-gray-50 px-6 py-3 dark:border-gray-800 dark:bg-gray-900">
            <TableRow>
              <TableCell
                isHeader
                className="px-4 py-3 text-start text-theme-xs font-medium text-gray-500 sm:px-6 dark:text-gray-400"
              >
                <div className="flex items-center gap-3">
                  <div>
                    <Checkbox checked={selectAll} onChange={handleSelectAll} />
                  </div>
                  <div>
                    <span className="text-theme-xs font-medium text-gray-500 dark:text-gray-400">
                      {t("crm.recentOrders.dealId")}
                    </span>
                  </div>
                </div>
              </TableCell>
              <TableCell
                isHeader
                className="px-6 py-3 text-start text-theme-xs font-medium text-gray-500 sm:px-6 dark:text-gray-400"
              >
                {t("crm.recentOrders.customer")}
              </TableCell>
              <TableCell
                isHeader
                className="px-6 py-3 text-start text-theme-xs font-medium text-gray-500 sm:px-6 dark:text-gray-400"
              >
                {t("crm.recentOrders.productService")}
              </TableCell>
              <TableCell
                isHeader
                className="px-6 py-3 text-start text-theme-xs font-medium text-gray-500 sm:px-6 dark:text-gray-400"
              >
                {t("crm.recentOrders.dealValue")}
              </TableCell>
              <TableCell
                isHeader
                className="px-6 py-3 text-start text-theme-xs font-medium text-gray-500 sm:px-6 dark:text-gray-400"
              >
                {t("crm.recentOrders.closeDate")}
              </TableCell>
              <TableCell
                isHeader
                className="px-6 py-3 text-start text-theme-xs font-medium text-gray-500 sm:px-6 dark:text-gray-400"
              >
                {t("crm.recentOrders.status")}
              </TableCell>
              <TableCell
                isHeader
                className="px-6 py-3 text-start text-theme-xs font-medium text-gray-500 sm:px-6 dark:text-gray-400"
              >
                {t("crm.recentOrders.action")}
              </TableCell>
            </TableRow>
          </TableHeader>
          <TableBody>
            {tableRowData.map((row: TableRowData) => (
              <TableRow key={row.id}>
                <TableCell className="px-4 py-3.5 sm:px-6">
                  <div className="flex items-center gap-3">
                    <div>
                      <Checkbox
                        checked={selectedRows.includes(row.id)}
                        onChange={() => handleRowSelect(row.id)}
                      />
                    </div>
                    <div>
                      <span className="block text-theme-sm font-medium text-gray-700 dark:text-gray-400">
                        {row.id}
                      </span>
                    </div>
                  </div>
                </TableCell>
                <TableCell className="px-4 py-3.5 sm:px-6">
                  <div className="flex items-center gap-3">
                    <AvatarText name={row.user.name} className="h-10 w-10" />
                    <div>
                      <span className="mb-0.5 block text-theme-sm font-medium text-gray-700 dark:text-gray-400">
                        {row.user.name}
                      </span>
                      <span className="text-theme-sm text-gray-500 dark:text-gray-400">
                        {row.user.email}
                      </span>
                    </div>
                  </div>
                </TableCell>
                <TableCell className="px-4 py-3.5 sm:px-6">
                  <p className="text-theme-sm text-gray-700 dark:text-gray-400">
                    {t(`crm.recentOrders.products.${row.product.nameKey}`)}
                  </p>
                </TableCell>
                <TableCell className="px-4 py-3.5 sm:px-6">
                  <p className="text-theme-sm text-gray-700 dark:text-gray-400">
                    {row.product.price}
                  </p>
                </TableCell>
                <TableCell className="px-4 py-3.5 sm:px-6">
                  <p className="text-theme-sm text-gray-700 dark:text-gray-400">
                    {row.product.purchaseDate}
                  </p>
                </TableCell>
                <TableCell className="px-4 py-3.5 sm:px-6">
                  <Badge
                    variant="light"
                    color={
                      row.status.type === "complete"
                        ? "success"
                        : row.status.type === "pending"
                          ? "warning"
                          : "error"
                    }
                    size="sm"
                  >
                    {t(`crm.recentOrders.statuses.${row.status.type}`)}
                  </Badge>
                </TableCell>
                <TableCell className="px-4 py-3.5 sm:px-6">
                  {row.actions.delete && (
                    <button>
                      <TrashBinIcon className="cursor-pointer text-gray-700 hover:text-error-500 dark:text-gray-400 dark:hover:text-error-500" />
                    </button>
                  )}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}
