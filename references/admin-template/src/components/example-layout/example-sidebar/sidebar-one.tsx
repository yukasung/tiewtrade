import { useSidebar } from "@/context/SidebarContext";
import {
  AiIcon,
  CalendarAltIcon,
  CartIcon,
  DashboardAltIcon,
  HorizontaLDots,
  ListIcon,
  MinusAltIcon,
  PageIcon,
  PlusAltIcon,
  ProfileAltIcon,
  TableIcon,
  TaskIcon,
} from "@/icons";
import { cn } from "@/utils";
import { useCallback, useEffect, useState } from "react";
import { Link, useLocation } from "react-router";

export default function SidebarOne() {
  const { isExpanded, isMobileOpen, isHovered, setIsHovered, setIsMobileOpen } =
    useSidebar();
  const location = useLocation();

  const [selected, setSelected] = useState<string>("Dashboard");
  const [subSelected, setSubSelected] = useState<string>("");

  const isActive = useCallback(
    (path: string) => location.pathname === path,
    [location.pathname],
  );

  // Auto-close sidebar on mobile after route change
  useEffect(() => {
    if (isMobileOpen) {
      setIsMobileOpen(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [location.pathname]);

  const handleMenuToggle = (name: string) => {
    setSelected((prev) => (prev === name ? "" : name));
  };

  const handleSubMenuToggle = (name: string) => {
    setSubSelected((prev) => (prev === name ? "" : name));
  };

  const showContent = isExpanded || isHovered || isMobileOpen;

  // Auto-expand active menu when sidebar is visible, close all when collapsed
  useEffect(() => {
    if (!showContent) {
      setSelected("");
      setSubSelected("");
      return;
    }

    const path = location.pathname;

    // Dashboard group
    if (
      [
        "/",
        "/analytics",
        "/marketing",
        "/stocks",
        "/saas",
        "/logistics",
        "/ai",
      ].includes(path)
    ) {
      setSelected("Dashboard");
    } else if (
      [
        "/inventory-management",
        "/product-development",
        "/finance",
        "/human-resources",
        "/supply-chain",
      ].includes(path)
    ) {
      setSelected("Dashboard");
      setSubSelected("CRM");
    }
    // AI Assistant group
    else if (
      [
        "/text-generator",
        "/image-generator",
        "/code-generator",
        "/video-generator",
      ].includes(path)
    ) {
      setSelected("AI");
    }
    // E-commerce group
    else if (
      [
        "/products-list",
        "/add-product",
        "/billing",
        "/transactions",
        "/single-transaction",
      ].includes(path)
    ) {
      setSelected("E-commerce");
    } else if (
      ["/invoices", "/single-invoice", "/create-invoice"].includes(path)
    ) {
      setSelected("E-commerce");
      setSubSelected("Invoices");
    }
    // Task group
    else if (["/task-list", "/task-kanban"].includes(path)) {
      setSelected("Task");
    }
    // Forms group
    else if (["/form-elements", "/form-layout"].includes(path)) {
      setSelected("Forms");
    }
    // Tables group
    else if (["/basic-tables", "/data-tables"].includes(path)) {
      setSelected("Tables");
    }
    // Pages group
    else if (
      [
        "/file-manager",
        "/pricing-tables",
        "/faq",
        "/api-keys",
        "/integrations",
        "/blank",
        "/coming-soon",
        "/maintenance",
        "/success",
      ].includes(path)
    ) {
      setSelected("Pages");
    } else if (["/error-404", "/error-500", "/error-503"].includes(path)) {
      setSelected("Pages");
      setSubSelected("ErrorPages");
    }
  }, [showContent, location.pathname]);

  return (
    <aside
      className={cn(
        "fixed start-0 top-0 z-50 flex h-screen flex-col border-e border-gray-200 bg-white px-5 transition-all duration-300 ease-in-out xl:translate-x-0 xl:rtl:translate-x-0 dark:border-gray-800 dark:bg-gray-900",
        isExpanded || isMobileOpen
          ? "w-[290px]"
          : isHovered
            ? "w-[290px]"
            : "w-[90px]",
        isMobileOpen
          ? "translate-x-0"
          : "-translate-x-full rtl:translate-x-full",
      )}
      onMouseEnter={() => !isExpanded && setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
    >
      {/* SIDEBAR HEADER */}
      <div
        className={cn(
          "sidebar-header flex shrink-0 items-center gap-2 pt-8 pb-7",
          !isExpanded && !isHovered ? "xl:justify-center" : "justify-between",
        )}
      >
        <Link to="#">
          {showContent ? (
            <>
              <img
                className="dark:hidden"
                src="/images/logo/logo.svg"
                alt="Logo"
              />
              <img
                className="hidden dark:block"
                src="/images/logo/logo-dark.svg"
                alt="Logo"
              />
            </>
          ) : (
            <img src="/images/logo/logo-icon.svg" alt="Logo" />
          )}
        </Link>
      </div>
      {/* /SIDEBAR HEADER */}

      <div className="no-scrollbar min-h-0 flex-1 overflow-y-auto pb-4 duration-300 ease-linear">
        <nav>
          {/* Menu Group */}
          <div>
            <h3 className="mb-4 text-xs leading-[20px] text-gray-400 uppercase">
              {showContent ? (
                "MENU"
              ) : (
                <HorizontaLDots className="mx-auto size-6" />
              )}
            </h3>

            <ul className="mb-6 flex flex-col gap-1">
              {/* ===== Dashboard ===== */}
              <li>
                <button
                  onClick={() => handleMenuToggle("Dashboard")}
                  className={`group menu-item ${
                    selected === "Dashboard"
                      ? "menu-item-active"
                      : "menu-item-inactive"
                  } w-full cursor-pointer`}
                >
                  <DashboardAltIcon
                    className={
                      selected === "Dashboard"
                        ? "menu-item-icon-active"
                        : "menu-item-icon-inactive"
                    }
                    width="24"
                    height="24"
                  />
                  {showContent && (
                    <span className="menu-item-text">Dashboard</span>
                  )}
                  {showContent &&
                    (selected === "Dashboard" ? (
                      <MinusAltIcon className="ms-auto h-5 w-5 text-brand-500" />
                    ) : (
                      <PlusAltIcon className="ms-auto h-5 w-5" />
                    ))}
                </button>

                {/* Dashboard Dropdown */}
                <div
                  className={`menu-accordion ${selected === "Dashboard" ? "open" : ""} ${!showContent ? "hidden" : ""}`}
                >
                  <div>
                    <ul className="menu-dropdown ms-6 mt-2 flex flex-col gap-1 border-s border-gray-200 ps-4 dark:border-gray-800">
                      <li>
                        <Link
                          to="#"
                          className={`group menu-dropdown-item ${
                            isActive("/")
                              ? "menu-dropdown-item-active"
                              : "menu-dropdown-item-inactive"
                          }`}
                        >
                          Ecommerce
                        </Link>
                      </li>
                      <li>
                        <Link
                          to="#"
                          className={`group menu-dropdown-item ${
                            isActive("/analytics")
                              ? "menu-dropdown-item-active"
                              : "menu-dropdown-item-inactive"
                          }`}
                        >
                          Analytics
                        </Link>
                      </li>
                      <li>
                        <Link
                          to="#"
                          className={`group menu-dropdown-item ${
                            isActive("/marketing")
                              ? "menu-dropdown-item-active"
                              : "menu-dropdown-item-inactive"
                          }`}
                        >
                          Marketing
                        </Link>
                      </li>
                      {/* CRM nested submenu */}
                      <li>
                        <button
                          onClick={() => handleSubMenuToggle("CRM")}
                          className={`group menu-dropdown-item flex w-full items-center justify-between ${
                            isActive("/crm")
                              ? "menu-dropdown-item-active"
                              : "menu-dropdown-item-inactive"
                          }`}
                        >
                          CRM
                          {subSelected === "CRM" ? (
                            <MinusAltIcon className="h-5 w-5 text-brand-500" />
                          ) : (
                            <PlusAltIcon className="h-5 w-5" />
                          )}
                        </button>
                        <div
                          className={`menu-accordion ${
                            subSelected === "CRM" ? "open" : ""
                          }`}
                        >
                          <div>
                            <ul className="mt-2 flex flex-col gap-1 border-s border-gray-200 ps-4 dark:border-gray-800">
                              <li>
                                <Link
                                  to="#"
                                  className={`group menu-dropdown-item ${
                                    isActive("/inventory-management")
                                      ? "menu-dropdown-item-active"
                                      : "menu-dropdown-item-inactive"
                                  }`}
                                >
                                  Inventory Management
                                </Link>
                              </li>
                              <li>
                                <Link
                                  to="#"
                                  className={`group menu-dropdown-item ${
                                    isActive("/product-development")
                                      ? "menu-dropdown-item-active"
                                      : "menu-dropdown-item-inactive"
                                  }`}
                                >
                                  Product Development
                                </Link>
                              </li>
                              <li>
                                <Link
                                  to="#"
                                  className={`group menu-dropdown-item ${
                                    isActive("/finance")
                                      ? "menu-dropdown-item-active"
                                      : "menu-dropdown-item-inactive"
                                  }`}
                                >
                                  Finance
                                </Link>
                              </li>
                              <li>
                                <Link
                                  to="#"
                                  className={`group menu-dropdown-item ${
                                    isActive("/human-resources")
                                      ? "menu-dropdown-item-active"
                                      : "menu-dropdown-item-inactive"
                                  }`}
                                >
                                  Human Resources
                                </Link>
                              </li>
                              <li>
                                <Link
                                  to="#"
                                  className={`group menu-dropdown-item ${
                                    isActive("/supply-chain")
                                      ? "menu-dropdown-item-active"
                                      : "menu-dropdown-item-inactive"
                                  }`}
                                >
                                  Supply Chain
                                </Link>
                              </li>
                            </ul>
                          </div>
                        </div>
                      </li>
                      <li>
                        <Link
                          to="#"
                          className={`group menu-dropdown-item ${
                            isActive("/stocks")
                              ? "menu-dropdown-item-active"
                              : "menu-dropdown-item-inactive"
                          }`}
                        >
                          Stocks
                          <span className="absolute end-3 flex items-center gap-1">
                            <span className="menu-dropdown-badge menu-dropdown-badge-inactive">
                              New
                            </span>
                          </span>
                        </Link>
                      </li>
                      <li>
                        <Link
                          to="#"
                          className={`group menu-dropdown-item ${
                            isActive("/saas")
                              ? "menu-dropdown-item-active"
                              : "menu-dropdown-item-inactive"
                          }`}
                        >
                          SaaS
                        </Link>
                      </li>
                      <li>
                        <Link
                          to="#"
                          className={`group menu-dropdown-item ${
                            isActive("/logistics")
                              ? "menu-dropdown-item-active"
                              : "menu-dropdown-item-inactive"
                          }`}
                        >
                          Logistics
                        </Link>
                      </li>
                      <li>
                        <Link
                          to="#"
                          className={`group menu-dropdown-item ${
                            isActive("/ai")
                              ? "menu-dropdown-item-active"
                              : "menu-dropdown-item-inactive"
                          }`}
                        >
                          AI
                        </Link>
                      </li>
                    </ul>
                  </div>
                </div>
              </li>
              {/* ===== /Dashboard ===== */}

              {/* ===== AI Assistant ===== */}
              <li>
                <button
                  onClick={() => handleMenuToggle("AI")}
                  className={`group menu-item ${
                    selected === "AI"
                      ? "menu-item-active"
                      : "menu-item-inactive"
                  } w-full cursor-pointer`}
                >
                  <AiIcon
                    className={
                      selected === "AI"
                        ? "menu-item-icon-active"
                        : "menu-item-icon-inactive"
                    }
                    width="24"
                    height="24"
                  />
                  {showContent && (
                    <span className="menu-item-text">AI Assistant</span>
                  )}
                  {showContent &&
                    (selected === "AI" ? (
                      <MinusAltIcon className="ms-auto h-5 w-5 text-brand-500" />
                    ) : (
                      <PlusAltIcon className="ms-auto h-5 w-5" />
                    ))}
                </button>

                <div
                  className={`menu-accordion ${selected === "AI" ? "open" : ""} ${!showContent ? "hidden" : ""}`}
                >
                  <div>
                    <ul className="menu-dropdown ms-6 mt-2 flex flex-col gap-1 border-s border-gray-200 ps-4 dark:border-gray-800">
                      <li>
                        <Link
                          to="#"
                          className={`group menu-dropdown-item ${
                            isActive("/text-generator")
                              ? "menu-dropdown-item-active"
                              : "menu-dropdown-item-inactive"
                          }`}
                        >
                          Text Generator
                        </Link>
                      </li>
                      <li>
                        <Link
                          to="#"
                          className={`group menu-dropdown-item ${
                            isActive("/image-generator")
                              ? "menu-dropdown-item-active"
                              : "menu-dropdown-item-inactive"
                          }`}
                        >
                          Image Generator
                        </Link>
                      </li>
                      <li>
                        <Link
                          to="#"
                          className={`group menu-dropdown-item ${
                            isActive("/code-generator")
                              ? "menu-dropdown-item-active"
                              : "menu-dropdown-item-inactive"
                          }`}
                        >
                          Code Generator
                        </Link>
                      </li>
                      <li>
                        <Link
                          to="#"
                          className={`group menu-dropdown-item ${
                            isActive("/video-generator")
                              ? "menu-dropdown-item-active"
                              : "menu-dropdown-item-inactive"
                          }`}
                        >
                          Video Generator
                        </Link>
                      </li>
                    </ul>
                  </div>
                </div>
              </li>
              {/* ===== /AI Assistant ===== */}

              {/* ===== E-commerce ===== */}
              <li>
                <button
                  onClick={() => handleMenuToggle("E-commerce")}
                  className={`group menu-item ${
                    selected === "E-commerce"
                      ? "menu-item-active"
                      : "menu-item-inactive"
                  } w-full cursor-pointer`}
                >
                  <CartIcon
                    className={
                      selected === "E-commerce"
                        ? "menu-item-icon-active"
                        : "menu-item-icon-inactive"
                    }
                    width="24"
                    height="24"
                  />
                  {showContent && (
                    <span className="menu-item-text">E-commerce</span>
                  )}
                  {showContent &&
                    (selected === "E-commerce" ? (
                      <MinusAltIcon className="ms-auto h-5 w-5 text-brand-500" />
                    ) : (
                      <PlusAltIcon className="ms-auto h-5 w-5" />
                    ))}
                </button>

                <div
                  className={`menu-accordion ${selected === "E-commerce" ? "open" : ""} ${!showContent ? "hidden" : ""}`}
                >
                  <div>
                    <ul className="menu-dropdown ms-6 mt-2 flex flex-col gap-1 border-s border-gray-200 ps-4 dark:border-gray-800">
                      <li>
                        <Link
                          to="#"
                          className={`group menu-dropdown-item ${
                            isActive("/products-list")
                              ? "menu-dropdown-item-active"
                              : "menu-dropdown-item-inactive"
                          }`}
                        >
                          Products
                        </Link>
                      </li>
                      <li>
                        <Link
                          to="#"
                          className={`group menu-dropdown-item ${
                            isActive("/add-product")
                              ? "menu-dropdown-item-active"
                              : "menu-dropdown-item-inactive"
                          }`}
                        >
                          Add Product
                        </Link>
                      </li>
                      <li>
                        <Link
                          to="#"
                          className={`group menu-dropdown-item ${
                            isActive("/billing")
                              ? "menu-dropdown-item-active"
                              : "menu-dropdown-item-inactive"
                          }`}
                        >
                          Billing
                        </Link>
                      </li>
                      {/* Invoices nested submenu */}
                      <li>
                        <button
                          onClick={() => handleSubMenuToggle("Invoices")}
                          className={`group menu-dropdown-item flex w-full items-center justify-between ${
                            isActive("/invoices")
                              ? "menu-dropdown-item-active"
                              : "menu-dropdown-item-inactive"
                          }`}
                        >
                          Invoices
                          {subSelected === "Invoices" ? (
                            <MinusAltIcon className="h-4 w-4 text-brand-500" />
                          ) : (
                            <PlusAltIcon className="h-4 w-4" />
                          )}
                        </button>
                        <div
                          className={`menu-accordion ${
                            subSelected === "Invoices" ? "open" : ""
                          }`}
                        >
                          <div>
                            <ul className="mt-2 flex flex-col gap-1 border-s border-gray-200 ps-4 dark:border-gray-800">
                              <li>
                                <Link
                                  to="#"
                                  className={`group menu-dropdown-item ${
                                    isActive("/invoices")
                                      ? "menu-dropdown-item-active"
                                      : "menu-dropdown-item-inactive"
                                  }`}
                                >
                                  Invoices List
                                </Link>
                              </li>
                              <li>
                                <Link
                                  to="#"
                                  className={`group menu-dropdown-item ${
                                    isActive("/single-invoice")
                                      ? "menu-dropdown-item-active"
                                      : "menu-dropdown-item-inactive"
                                  }`}
                                >
                                  Single Invoice
                                </Link>
                              </li>
                              <li>
                                <Link
                                  to="#"
                                  className={`group menu-dropdown-item ${
                                    isActive("/create-invoice")
                                      ? "menu-dropdown-item-active"
                                      : "menu-dropdown-item-inactive"
                                  }`}
                                >
                                  Create Invoice
                                </Link>
                              </li>
                            </ul>
                          </div>
                        </div>
                      </li>
                      <li>
                        <Link
                          to="#"
                          className={`group menu-dropdown-item ${
                            isActive("/transactions")
                              ? "menu-dropdown-item-active"
                              : "menu-dropdown-item-inactive"
                          }`}
                        >
                          Transactions
                        </Link>
                      </li>
                      <li>
                        <Link
                          to="#"
                          className={`group menu-dropdown-item ${
                            isActive("/single-transaction")
                              ? "menu-dropdown-item-active"
                              : "menu-dropdown-item-inactive"
                          }`}
                        >
                          Single Transaction
                        </Link>
                      </li>
                    </ul>
                  </div>
                </div>
              </li>
              {/* ===== /E-commerce ===== */}

              {/* ===== Calendar ===== */}
              <li>
                <Link
                  to="#"
                  className={`group menu-item ${
                    isActive("/calendar")
                      ? "menu-item-active"
                      : "menu-item-inactive"
                  }`}
                >
                  <CalendarAltIcon
                    className={
                      isActive("/calendar")
                        ? "menu-item-icon-active"
                        : "menu-item-icon-inactive"
                    }
                    width="24"
                    height="24"
                  />
                  {showContent && (
                    <span className="menu-item-text">Calendar</span>
                  )}
                </Link>
              </li>
              {/* ===== /Calendar ===== */}

              {/* ===== User Profile ===== */}
              <li>
                <Link
                  to="#"
                  className={`group menu-item ${
                    isActive("/profile")
                      ? "menu-item-active"
                      : "menu-item-inactive"
                  }`}
                >
                  <ProfileAltIcon
                    className={
                      isActive("/profile")
                        ? "menu-item-icon-active"
                        : "menu-item-icon-inactive"
                    }
                    width="24"
                    height="24"
                  />
                  {showContent && (
                    <span className="menu-item-text">User Profile</span>
                  )}
                </Link>
              </li>
              {/* ===== /User Profile ===== */}

              {/* ===== Task ===== */}
              <li>
                <button
                  onClick={() => handleMenuToggle("Task")}
                  className={`group menu-item ${
                    selected === "Task"
                      ? "menu-item-active"
                      : "menu-item-inactive"
                  } w-full cursor-pointer`}
                >
                  <TaskIcon
                    className={
                      selected === "Task"
                        ? "menu-item-icon-active"
                        : "menu-item-icon-inactive"
                    }
                    width="24"
                    height="24"
                  />
                  {showContent && <span className="menu-item-text">Task</span>}
                  {showContent &&
                    (selected === "Task" ? (
                      <MinusAltIcon className="ms-auto h-5 w-5 text-brand-500" />
                    ) : (
                      <PlusAltIcon className="ms-auto h-5 w-5" />
                    ))}
                </button>

                <div
                  className={`menu-accordion ${selected === "Task" ? "open" : ""} ${!showContent ? "hidden" : ""}`}
                >
                  <div>
                    <ul className="menu-dropdown ms-6 mt-2 flex flex-col gap-1 border-s border-gray-200 ps-4 dark:border-gray-800">
                      <li>
                        <Link
                          to="#"
                          className={`group menu-dropdown-item ${
                            isActive("/task-list")
                              ? "menu-dropdown-item-active"
                              : "menu-dropdown-item-inactive"
                          }`}
                        >
                          List
                        </Link>
                      </li>
                      <li>
                        <Link
                          to="#"
                          className={`group menu-dropdown-item ${
                            isActive("/task-kanban")
                              ? "menu-dropdown-item-active"
                              : "menu-dropdown-item-inactive"
                          }`}
                        >
                          Kanban
                        </Link>
                      </li>
                    </ul>
                  </div>
                </div>
              </li>
              {/* ===== /Task ===== */}

              {/* ===== Forms ===== */}
              <li>
                <button
                  onClick={() => handleMenuToggle("Forms")}
                  className={`group menu-item ${
                    selected === "Forms"
                      ? "menu-item-active"
                      : "menu-item-inactive"
                  } w-full cursor-pointer`}
                >
                  <ListIcon
                    className={
                      selected === "Forms"
                        ? "menu-item-icon-active"
                        : "menu-item-icon-inactive"
                    }
                    width="24"
                    height="24"
                  />
                  {showContent && <span className="menu-item-text">Forms</span>}
                  {showContent &&
                    (selected === "Forms" ? (
                      <MinusAltIcon className="ms-auto h-5 w-5 text-brand-500" />
                    ) : (
                      <PlusAltIcon className="ms-auto h-5 w-5" />
                    ))}
                </button>

                <div
                  className={`menu-accordion ${selected === "Forms" ? "open" : ""} ${!showContent ? "hidden" : ""}`}
                >
                  <div>
                    <ul className="menu-dropdown ms-6 mt-2 flex flex-col gap-1 border-s border-gray-200 ps-4 dark:border-gray-800">
                      <li>
                        <Link
                          to="#"
                          className={`group menu-dropdown-item ${
                            isActive("/form-elements")
                              ? "menu-dropdown-item-active"
                              : "menu-dropdown-item-inactive"
                          }`}
                        >
                          Form Elements
                        </Link>
                      </li>
                      <li>
                        <Link
                          to="#"
                          className={`group menu-dropdown-item ${
                            isActive("/form-layout")
                              ? "menu-dropdown-item-active"
                              : "menu-dropdown-item-inactive"
                          }`}
                        >
                          Form Layout
                        </Link>
                      </li>
                    </ul>
                  </div>
                </div>
              </li>
              {/* ===== /Forms ===== */}

              {/* ===== Tables ===== */}
              <li>
                <button
                  onClick={() => handleMenuToggle("Tables")}
                  className={`group menu-item ${
                    selected === "Tables"
                      ? "menu-item-active"
                      : "menu-item-inactive"
                  } w-full cursor-pointer`}
                >
                  <TableIcon
                    className={
                      selected === "Tables"
                        ? "menu-item-icon-active"
                        : "menu-item-icon-inactive"
                    }
                    width="24"
                    height="24"
                  />
                  {showContent && (
                    <span className="menu-item-text">Tables</span>
                  )}
                  {showContent &&
                    (selected === "Tables" ? (
                      <MinusAltIcon className="ms-auto h-5 w-5 text-brand-500" />
                    ) : (
                      <PlusAltIcon className="ms-auto h-5 w-5" />
                    ))}
                </button>

                <div
                  className={`menu-accordion ${selected === "Tables" ? "open" : ""} ${!showContent ? "hidden" : ""}`}
                >
                  <div>
                    <ul className="menu-dropdown ms-6 mt-2 flex flex-col gap-1 border-s border-gray-200 ps-4 dark:border-gray-800">
                      <li>
                        <Link
                          to="#"
                          className={`group menu-dropdown-item ${
                            isActive("/basic-tables")
                              ? "menu-dropdown-item-active"
                              : "menu-dropdown-item-inactive"
                          }`}
                        >
                          Basic Tables
                        </Link>
                      </li>
                      <li>
                        <Link
                          to="#"
                          className={`group menu-dropdown-item ${
                            isActive("/data-tables")
                              ? "menu-dropdown-item-active"
                              : "menu-dropdown-item-inactive"
                          }`}
                        >
                          Data Tables
                        </Link>
                      </li>
                    </ul>
                  </div>
                </div>
              </li>
              {/* ===== /Tables ===== */}

              {/* ===== Pages ===== */}
              <li>
                <button
                  onClick={() => handleMenuToggle("Pages")}
                  className={`group menu-item ${
                    selected === "Pages"
                      ? "menu-item-active"
                      : "menu-item-inactive"
                  } w-full cursor-pointer`}
                >
                  <PageIcon
                    className={
                      selected === "Pages"
                        ? "menu-item-icon-active"
                        : "menu-item-icon-inactive"
                    }
                    width="24"
                    height="24"
                  />
                  {showContent && <span className="menu-item-text">Pages</span>}
                  {showContent &&
                    (selected === "Pages" ? (
                      <MinusAltIcon className="ms-auto h-5 w-5 text-brand-500" />
                    ) : (
                      <PlusAltIcon className="ms-auto h-5 w-5" />
                    ))}
                </button>

                <div
                  className={`menu-accordion ${selected === "Pages" ? "open" : ""} ${!showContent ? "hidden" : ""}`}
                >
                  <div>
                    <ul className="menu-dropdown ms-6 mt-2 flex flex-col gap-1 border-s border-gray-200 ps-4 dark:border-gray-800">
                      <li>
                        <Link
                          to="#"
                          className={`group menu-dropdown-item ${
                            isActive("/file-manager")
                              ? "menu-dropdown-item-active"
                              : "menu-dropdown-item-inactive"
                          }`}
                        >
                          File Manager
                        </Link>
                      </li>
                      <li>
                        <Link
                          to="#"
                          className={`group menu-dropdown-item ${
                            isActive("/pricing-tables")
                              ? "menu-dropdown-item-active"
                              : "menu-dropdown-item-inactive"
                          }`}
                        >
                          Pricing Tables
                        </Link>
                      </li>
                      <li>
                        <Link
                          to="#"
                          className={`group menu-dropdown-item ${
                            isActive("/faq")
                              ? "menu-dropdown-item-active"
                              : "menu-dropdown-item-inactive"
                          }`}
                        >
                          FAQ
                        </Link>
                      </li>
                      <li>
                        <Link
                          to="#"
                          className={`group menu-dropdown-item ${
                            isActive("/api-keys")
                              ? "menu-dropdown-item-active"
                              : "menu-dropdown-item-inactive"
                          }`}
                        >
                          API Keys
                          <span className="absolute end-3 flex items-center gap-1">
                            <span className="menu-dropdown-badge menu-dropdown-badge-inactive">
                              New
                            </span>
                          </span>
                        </Link>
                      </li>
                      <li>
                        <Link
                          to="#"
                          className={`group menu-dropdown-item ${
                            isActive("/integrations")
                              ? "menu-dropdown-item-active"
                              : "menu-dropdown-item-inactive"
                          }`}
                        >
                          Integrations
                          <span className="absolute end-3 flex items-center gap-1">
                            <span className="menu-dropdown-badge menu-dropdown-badge-inactive">
                              New
                            </span>
                          </span>
                        </Link>
                      </li>
                      <li>
                        <Link
                          to="#"
                          className={`group menu-dropdown-item ${
                            isActive("/blank")
                              ? "menu-dropdown-item-active"
                              : "menu-dropdown-item-inactive"
                          }`}
                        >
                          Blank Page
                        </Link>
                      </li>
                      {/* Error Pages nested submenu */}
                      <li>
                        <button
                          onClick={() => handleSubMenuToggle("ErrorPages")}
                          className={`group menu-dropdown-item flex w-full items-center justify-between ${
                            isActive("/error-404") ||
                            isActive("/error-500") ||
                            isActive("/error-503")
                              ? "menu-dropdown-item-active"
                              : "menu-dropdown-item-inactive"
                          }`}
                        >
                          Error Pages
                          {subSelected === "ErrorPages" ? (
                            <MinusAltIcon className="h-4 w-4 text-brand-500" />
                          ) : (
                            <PlusAltIcon className="h-4 w-4" />
                          )}
                        </button>
                        <div
                          className={`menu-accordion ${
                            subSelected === "ErrorPages" ? "open" : ""
                          }`}
                        >
                          <div>
                            <ul className="mt-2 flex flex-col gap-1 border-s border-gray-200 ps-4 dark:border-gray-800">
                              <li>
                                <Link
                                  to="#"
                                  className={`group menu-dropdown-item ${
                                    isActive("/error-404")
                                      ? "menu-dropdown-item-active"
                                      : "menu-dropdown-item-inactive"
                                  }`}
                                >
                                  404 Error
                                </Link>
                              </li>
                              <li>
                                <Link
                                  to="#"
                                  className={`group menu-dropdown-item ${
                                    isActive("/error-500")
                                      ? "menu-dropdown-item-active"
                                      : "menu-dropdown-item-inactive"
                                  }`}
                                >
                                  500 Error
                                </Link>
                              </li>
                              <li>
                                <Link
                                  to="#"
                                  className={`group menu-dropdown-item ${
                                    isActive("/error-503")
                                      ? "menu-dropdown-item-active"
                                      : "menu-dropdown-item-inactive"
                                  }`}
                                >
                                  503 Error
                                </Link>
                              </li>
                            </ul>
                          </div>
                        </div>
                      </li>
                      <li>
                        <Link
                          to="#"
                          className={`group menu-dropdown-item ${
                            isActive("/coming-soon")
                              ? "menu-dropdown-item-active"
                              : "menu-dropdown-item-inactive"
                          }`}
                        >
                          Coming Soon
                        </Link>
                      </li>
                      <li>
                        <Link
                          to="#"
                          className={`group menu-dropdown-item ${
                            isActive("/maintenance")
                              ? "menu-dropdown-item-active"
                              : "menu-dropdown-item-inactive"
                          }`}
                        >
                          Maintenance
                        </Link>
                      </li>
                      <li>
                        <Link
                          to="#"
                          className={`group menu-dropdown-item ${
                            isActive("/success")
                              ? "menu-dropdown-item-active"
                              : "menu-dropdown-item-inactive"
                          }`}
                        >
                          Success
                        </Link>
                      </li>
                    </ul>
                  </div>
                </div>
              </li>
              {/* ===== /Pages ===== */}
            </ul>
          </div>
        </nav>
      </div>
    </aside>
  );
}
