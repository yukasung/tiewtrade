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
import { useTranslation } from "react-i18next";

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
  status: "Success" | "Pending" | "Failed";
}

export default function FeaturedCampaign() {
  const { t } = useTranslation();
  const [isOpen, setIsOpen] = useState(false);

  function toggleDropdown() {
    setIsOpen(!isOpen);
  }

  function closeDropdown() {
    setIsOpen(false);
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
        name: t("marketing.featuredCampaign.campaigns.growBrand"),
        type: t("marketing.featuredCampaign.adsCampaign"),
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
        name: t("marketing.featuredCampaign.campaigns.betterIdeas"),
        type: t("marketing.featuredCampaign.adsCampaign"),
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
        name: t("marketing.featuredCampaign.campaigns.increaseTraffic"),
        type: t("marketing.featuredCampaign.adsCampaign"),
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
        name: t("marketing.featuredCampaign.campaigns.growBrand"),
        type: t("marketing.featuredCampaign.adsCampaign"),
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
        name: t("marketing.featuredCampaign.campaigns.growBrand"),
        type: t("marketing.featuredCampaign.adsCampaign"),
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
        name: t("marketing.featuredCampaign.campaigns.growBrand"),
        type: t("marketing.featuredCampaign.adsCampaign"),
      },
      status: "Success",
    },
  ];

  return (
    <div className="overflow-hidden rounded-2xl border border-gray-200 bg-white px-5 pt-4 pb-3 sm:px-6 dark:border-gray-800 dark:bg-white/3">
      <div className="mb-4 flex justify-between gap-2 sm:items-center">
        <div>
          <h3 className="text-lg font-semibold text-gray-800 dark:text-white/90">
            {t("marketing.featuredCampaign.title")}
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
              {t("common.viewMore")}
            </DropdownItem>
            <DropdownItem
              onItemClick={closeDropdown}
              className="flex w-full rounded-lg text-start font-normal text-gray-500 hover:bg-gray-100 hover:text-gray-700 dark:text-gray-400 dark:hover:bg-white/5 dark:hover:text-gray-300"
            >
              {t("common.delete")}
            </DropdownItem>
          </Dropdown>
        </div>
      </div>

      <div className="custom-scrollbar max-w-full overflow-x-auto">
        <div className="min-w-[617px] 2xl:min-w-[808px]">
          <Table>
            <TableHeader className="border-y border-gray-100 dark:border-gray-800">
              <TableRow>
                <TableCell
                  isHeader
                  className="py-3 text-start text-theme-xs font-medium text-gray-500 dark:text-gray-400"
                >
                  {t("marketing.featuredCampaign.products")}
                </TableCell>
                <TableCell
                  isHeader
                  className="py-3 text-start text-theme-xs font-medium text-gray-500 dark:text-gray-400"
                >
                  {t("marketing.featuredCampaign.campaign")}
                </TableCell>
                <TableCell
                  isHeader
                  className="py-3 text-start text-theme-xs font-medium text-gray-500 dark:text-gray-400"
                >
                  {t("marketing.featuredCampaign.status")}
                </TableCell>
              </TableRow>
            </TableHeader>

            <TableBody className="divide-y divide-gray-100 dark:divide-gray-800">
              {campaigns.map((item) => (
                <TableRow key={item.id} className="">
                  <TableCell className="py-3">
                    <div className="flex items-center gap-[18px]">
                      <div className="h-10 w-10 overflow-hidden rounded-full">
                        <img src={item.creator.image} alt="user" />
                      </div>
                      <div>
                        <p className="text-theme-sm text-gray-700 dark:text-gray-400">
                          {item.creator.name}
                        </p>
                      </div>
                    </div>
                  </TableCell>
                  <TableCell className="py-3">
                    <div className="flex w-full items-center gap-5">
                      <div className="w-full max-w-8">
                        <img src={item.campaign.image} alt="brand" />
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
                  <TableCell className="py-3">
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
                      {item.status === "Success"
                        ? t("marketing.featuredCampaign.statuses.success")
                        : item.status === "Pending"
                          ? t("marketing.featuredCampaign.statuses.pending")
                          : t("marketing.featuredCampaign.statuses.failed")}
                    </Badge>
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
