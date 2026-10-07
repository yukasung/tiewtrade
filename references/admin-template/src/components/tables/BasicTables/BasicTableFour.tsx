"use client";
import Badge from "@/components/ui/badge/Badge";
import { Dropdown } from "@/components/ui/dropdown/Dropdown";
import { DropdownItem } from "@/components/ui/dropdown/DropdownItem";
import {
  Table,
  TableBody,
  TableCell,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { MoreDotIcon } from "@/icons";
import { useState } from "react";

interface Campaign {
  id: number;
  creator: {
    image: string;
    name: string;
  };
  campaign: {
    image: string;
    name: string;
    type: string;
  };
  status: string;
}

const campaigns: Campaign[] = [
  {
    id: 1,
    creator: {
      image: "/images/user/user-01.jpg",
      name: "Wilson Gouse",
    },
    campaign: {
      image: "/images/brand/brand-01.svg",
      name: "Grow your brand by...",
      type: "Ads campaign",
    },
    status: "Success",
  },
  {
    id: 2,
    creator: {
      image: "/images/user/user-02.jpg",
      name: "Wilson Gouse",
    },
    campaign: {
      image: "/images/brand/brand-02.svg",
      name: "Make Better Ideas...",
      type: "Ads campaign",
    },
    status: "Pending",
  },
  {
    id: 3,
    creator: {
      image: "/images/user/user-03.jpg",
      name: "Wilson Gouse",
    },
    campaign: {
      image: "/images/brand/brand-03.svg",
      name: "Increase your website tra...",
      type: "Ads campaign",
    },
    status: "Success",
  },
  {
    id: 4,
    creator: {
      image: "/images/user/user-04.jpg",
      name: "Wilson Gouse",
    },
    campaign: {
      image: "/images/brand/brand-04.svg",
      name: "Grow your brand by...",
      type: "Ads campaign",
    },
    status: "Failed",
  },
  {
    id: 5,
    creator: {
      image: "/images/user/user-05.jpg",
      name: "Wilson Gouse",
    },
    campaign: {
      image: "/images/brand/brand-05.svg",
      name: "Grow your brand by...",
      type: "Ads campaign",
    },
    status: "Success",
  },
  {
    id: 6,
    creator: {
      image: "/images/user/user-06.jpg",
      name: "Wilson Gouse",
    },
    campaign: {
      image: "/images/brand/brand-06.svg",
      name: "Grow your brand by...",
      type: "Ads campaign",
    },
    status: "Success",
  },
];

export default function BasicTableFour() {
  const [isOpen, setIsOpen] = useState(false);

  function toggleDropdown() {
    setIsOpen(!isOpen);
  }

  function closeDropdown() {
    setIsOpen(false);
  }
  return (
    <div className="overflow-hidden rounded-2xl border border-gray-200 bg-white px-5 pt-4 pb-3 sm:px-6 dark:border-white/[0.05] dark:bg-white/3">
      <div className="mb-4 flex justify-between gap-2 sm:items-center">
        <div>
          <h3 className="text-lg font-semibold text-gray-800 dark:text-white/90">
            Featured Campaigns
          </h3>
        </div>

        <div className="relative inline-block">
          <button className="dropdown-toggle" onClick={toggleDropdown}>
            <MoreDotIcon className="size-6 text-gray-400 hover:text-gray-700 dark:hover:text-gray-300" />
          </button>
          <Dropdown
            isOpen={isOpen}
            onClose={closeDropdown}
            className="w-40 p-2"
          >
            <DropdownItem
              onItemClick={closeDropdown}
              className="flex w-full rounded-lg text-start font-normal text-gray-500 hover:bg-gray-100 hover:text-gray-700 dark:text-gray-400 dark:hover:bg-white/5 dark:hover:text-gray-300"
            >
              View More
            </DropdownItem>
            <DropdownItem
              onItemClick={closeDropdown}
              className="flex w-full rounded-lg text-start font-normal text-gray-500 hover:bg-gray-100 hover:text-gray-700 dark:text-gray-400 dark:hover:bg-white/5 dark:hover:text-gray-300"
            >
              Delete
            </DropdownItem>
          </Dropdown>
        </div>
      </div>

      <div className="max-w-full overflow-x-auto">
        <Table>
          <TableHeader className="border-y border-gray-100 dark:border-white/[0.05]">
            <TableRow>
              <TableCell
                isHeader
                className="px-4 py-3 text-start text-theme-xs font-medium text-gray-500 first:ps-0 last:pe-0 dark:text-gray-400"
              >
                Products
              </TableCell>
              <TableCell
                isHeader
                className="px-4 py-3 text-start text-theme-xs font-medium text-gray-500 first:ps-0 last:pe-0 dark:text-gray-400"
              >
                Campaign
              </TableCell>
              <TableCell
                isHeader
                className="px-4 py-3 text-start text-theme-xs font-medium text-gray-500 first:ps-0 last:pe-0 dark:text-gray-400"
              >
                Status
              </TableCell>
            </TableRow>
          </TableHeader>

          <TableBody className="divide-y divide-gray-100 dark:divide-white/[0.05]">
            {campaigns.map((item) => (
              <TableRow key={item.id}>
                <TableCell className="px-4 py-3 text-start whitespace-nowrap first:ps-0 last:pe-0">
                  <div className="flex items-center gap-[18px]">
                    <div className="h-10 w-10 shrink-0 overflow-hidden rounded-full">
                      <img
                        width={40}
                        height={40}
                        className="size-10 w-full"
                        src={item.creator.image}
                        alt="user"
                      />
                    </div>
                    <div>
                      <p className="text-theme-sm text-gray-700 dark:text-gray-400">
                        {item.creator.name}
                      </p>
                    </div>
                  </div>
                </TableCell>
                <TableCell className="px-4 py-3 text-start whitespace-nowrap first:ps-0 last:pe-0">
                  <div className="flex w-full items-center gap-5">
                    <div className="w-full max-w-8">
                      <img
                        width={32}
                        height={32}
                        className="size-8 w-full"
                        src={item.campaign.image}
                        alt="brand"
                      />
                    </div>
                    <div className="truncate">
                      <p className="mb-0.5 truncate text-theme-sm font-medium text-gray-700 dark:text-gray-400">
                        {item.campaign.name}
                      </p>
                      <span className="text-theme-xs text-gray-500 dark:text-gray-400">
                        {item.campaign.type}
                      </span>
                    </div>
                  </div>
                </TableCell>
                <TableCell className="px-4 py-3 text-start whitespace-nowrap first:ps-0 last:pe-0">
                  <Badge
                    size="sm"
                    color={
                      item.status === "Success"
                        ? "success"
                        : item.status === "Pending"
                          ? "warning"
                          : "error"
                    }
                  >
                    {item.status}
                  </Badge>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}
