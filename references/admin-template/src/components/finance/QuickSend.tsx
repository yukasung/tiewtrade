import { useState, useRef, useEffect } from "react";
import { useTranslation } from "react-i18next";
import { useClickOutside } from "../../hooks/useClickOutside";

const users = [
  { id: 17, avatar: "/images/user/user-17.jpg" },
  { id: 18, avatar: "/images/user/user-18.jpg" },
  { id: 19, avatar: "/images/user/user-19.jpg" },
  { id: 20, avatar: "/images/user/user-20.jpg" },
  { id: 21, avatar: "/images/user/user-21.jpg" },
  { id: 22, avatar: "/images/user/user-22.jpg" },
  { id: 23, avatar: "/images/user/user-23.jpg" },
  { id: 24, avatar: "/images/user/user-24.jpg" },
  { id: 25, avatar: "/images/user/user-25.jpg" },
  { id: 26, avatar: "/images/user/user-26.jpg" },
];

export default function QuickSend() {
  const { t } = useTranslation();
  const [selectedUser, setSelectedUser] = useState(17);
  const [atStart, setAtStart] = useState(true);
  const [atEnd, setAtEnd] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  const [isSendFromOpen, setIsSendFromOpen] = useState(false);
  const [selectedSendFrom, setSelectedSendFrom] = useState(
    "Visa •••• •••• 3657"
  );

  const [isCurrencyOpen, setIsCurrencyOpen] = useState(false);
  const [selectedCurrency, setSelectedCurrency] = useState("$ USD");

  // Refs for outside click handling
  const sendFromDropdownRef = useRef<HTMLDivElement>(null);
  const currencyDropdownRef = useRef<HTMLDivElement>(null);

  // Close dropdowns on outside click
  useClickOutside(sendFromDropdownRef, () => setIsSendFromOpen(false));
  useClickOutside(currencyDropdownRef, () => setIsCurrencyOpen(false));

  const checkScroll = () => {
    if (scrollRef.current) {
      const { scrollLeft, clientWidth, scrollWidth } = scrollRef.current;
      setAtStart(scrollLeft <= 5);
      setAtEnd(scrollLeft + clientWidth >= scrollWidth - 5);
    }
  };

  useEffect(() => {
    checkScroll();
    window.addEventListener("resize", checkScroll);
    return () => window.removeEventListener("resize", checkScroll);
  }, []);

  const scrollNext = () => {
    scrollRef.current?.scrollBy({ left: 120, behavior: "smooth" });
  };

  const scrollPrev = () => {
    scrollRef.current?.scrollBy({ left: -120, behavior: "smooth" });
  };

  return (
    <div className="rounded-2xl border border-gray-200 bg-white p-6 md:col-span-1 dark:border-gray-800 dark:bg-white/3">
      <h3 className="mb-4 text-lg font-semibold text-gray-800 dark:text-white/90">
        {t("finance.quickSend.title")}
      </h3>

      {/* User Avatars */}
      <div className="relative mb-4">
        {/* Previous Arrow */}
        {!atStart && (
          <button
            type="button"
            onClick={scrollPrev}
            className="absolute top-1/2 start-0 z-20 flex size-8 -translate-y-1/2 items-center justify-center rounded-full text-gray-500 transition-all hover:bg-gray-100 dark:text-gray-400 dark:hover:bg-gray-800"
          >
            <svg
              className="rtl:rotate-180"
              width="18"
              height="18"
              viewBox="0 0 20 20"
              fill="none"
              xmlns="http://www.w3.org/2000/svg"
            >
              <path
                d="M12.5 15L7.5 10L12.5 5"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
          </button>
        )}

        {/* Left Mask */}
        {!atStart && (
          <div className="pointer-events-none absolute top-0 bottom-0 start-0 z-10 w-16 bg-gradient-to-r rtl:bg-gradient-to-l from-white via-white/80 to-transparent dark:from-[#1C2434] dark:via-[#1C2434]/80"></div>
        )}

        <div
          ref={scrollRef}
          onScroll={checkScroll}
          className="no-scrollbar flex items-center gap-3 overflow-x-hidden scroll-smooth px-0.5 py-1"
        >
          {users.map((user) => (
            <button
              key={user.id}
              type="button"
              onClick={() => setSelectedUser(user.id)}
              className={`relative flex size-10 shrink-0 items-center justify-center rounded-full p-0.5 transition-all ${
                selectedUser === user.id
                  ? "ring-1 ring-brand-500"
                  : "bg-gray-100 ring-0 hover:ring-1 hover:ring-brand-500 dark:bg-gray-800"
              }`}
            >
              <img
                className="size-full rounded-full object-cover"
                src={user.avatar}
                alt={`User ${user.id}`}
              />
            </button>
          ))}
        </div>

        {/* Right Mask */}
        {!atEnd && (
          <div className="pointer-events-none absolute top-0 end-0 bottom-0 z-10 w-16 bg-gradient-to-l rtl:bg-gradient-to-r from-white via-white/80 to-transparent dark:from-[#1C2434] dark:via-[#1C2434]/80"></div>
        )}

        {/* Next Arrow */}
        {!atEnd && (
          <button
            type="button"
            onClick={scrollNext}
            className="absolute top-1/2 end-0 z-20 flex size-8 -translate-y-1/2 items-center justify-center rounded-full text-gray-500 transition-all hover:bg-gray-100 dark:text-gray-400 dark:hover:bg-gray-800"
          >
            <svg
              className="rtl:rotate-180"
              width="18"
              height="18"
              viewBox="0 0 20 20"
              fill="none"
              xmlns="http://www.w3.org/2000/svg"
            >
              <path
                d="M7.5 15L12.5 10L7.5 5"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
          </button>
        )}
      </div>

      <form
        className="space-y-3"
        onSubmit={(e) => {
          e.preventDefault();
        }}
      >
        {/* Send From */}
        <div>
          <label className="mb-1.5 block text-sm font-medium text-gray-700 dark:text-gray-400">
            {t("finance.quickSend.sendFrom")}
          </label>
          <div className="relative" ref={sendFromDropdownRef}>
            <button
              type="button"
              onClick={() => setIsSendFromOpen(!isSendFromOpen)}
              className="flex h-10 w-full items-center justify-between rounded-lg border border-gray-300 bg-white px-4 py-3 text-sm font-normal text-gray-700 shadow-xs dark:border-gray-700 dark:bg-gray-900 dark:text-gray-300"
            >
              <span>{selectedSendFrom}</span>
              <svg
                className={`text-gray-700 transition-transform dark:text-gray-400 ${
                  isSendFromOpen ? "rotate-180" : ""
                }`}
                width="20"
                height="20"
                viewBox="0 0 20 20"
                fill="none"
                xmlns="http://www.w3.org/2000/svg"
              >
                <path
                  d="M4.79102 8.021L9.99935 13.2293L15.2077 8.021"
                  stroke="currentColor"
                  strokeWidth="1.5"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
            </button>
            {isSendFromOpen && (
              <div className="absolute start-0 z-10 mt-2 w-full rounded-xl border border-gray-200 bg-white p-2 shadow-lg dark:border-gray-700 dark:bg-gray-900">
                <button
                  type="button"
                  onClick={() => {
                    setSelectedSendFrom("Visa •••• •••• 3657");
                    setIsSendFromOpen(false);
                  }}
                  className="w-full rounded-lg px-3 py-2 text-start text-sm text-gray-700 hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-white/5"
                >
                  Visa •••• •••• 3657
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setSelectedSendFrom("Master •••• •••• 4912");
                    setIsSendFromOpen(false);
                  }}
                  className="w-full rounded-lg px-3 py-2 text-start text-sm text-gray-700 hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-white/5"
                >
                  Master •••• •••• 4912
                </button>
              </div>
            )}
          </div>
        </div>

        <div className="grid grid-cols-2 gap-3">
          {/* Currency */}
          <div>
            <label className="mb-1.5 block text-sm font-medium text-gray-700 dark:text-gray-400">
              {t("finance.quickSend.currency")}
            </label>
            <div className="relative" ref={currencyDropdownRef}>
              <button
                type="button"
                onClick={() => setIsCurrencyOpen(!isCurrencyOpen)}
                className="flex h-10 w-full items-center justify-between rounded-lg border border-gray-300 bg-white px-4 py-3 text-sm font-normal text-gray-700 shadow-xs dark:border-gray-700 dark:bg-gray-900 dark:text-gray-300"
              >
                <span>{selectedCurrency}</span>
                <svg
                  className={`transition-transform ${isCurrencyOpen ? "rotate-180" : ""}`}
                  width="20"
                  height="20"
                  viewBox="0 0 20 20"
                  fill="none"
                  xmlns="http://www.w3.org/2000/svg"
                >
                  <path
                    d="M5 7.5L10 12.5L15 7.5"
                    stroke="currentColor"
                    strokeWidth="1.5"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                </svg>
              </button>
              {isCurrencyOpen && (
                <div className="absolute start-0 z-10 mt-2 w-full rounded-lg border border-gray-200 bg-white p-2 shadow-lg dark:border-gray-700 dark:bg-gray-900">
                  <button
                    type="button"
                    onClick={() => {
                      setSelectedCurrency("$ USD");
                      setIsCurrencyOpen(false);
                    }}
                    className="w-full rounded-lg px-3 py-2 text-start text-sm text-gray-700 hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-white/5"
                  >
                    $ USD
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      setSelectedCurrency("€ EUR");
                      setIsCurrencyOpen(false);
                    }}
                    className="w-full rounded-lg px-3 py-2 text-start text-sm text-gray-700 hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-white/5"
                  >
                    € EUR
                  </button>
                </div>
              )}
            </div>
          </div>
          {/* Amount */}
          <div>
            <label className="mb-1.5 block text-sm font-medium text-gray-700 dark:text-gray-400">
              {t("finance.quickSend.amount")}
            </label>
            <input
              type="text"
              placeholder="0.00"
              className="focus:border-brand-500 focus:ring-brand-500 h-10 w-full rounded-lg border border-gray-300 bg-white px-4 py-3 text-sm text-gray-800 shadow-xs dark:border-gray-700 dark:bg-gray-900 dark:text-white/90"
            />
          </div>
        </div>

        <button
          type="submit"
          className="flex h-10 w-full items-center justify-center rounded-lg bg-brand-500 px-4 py-3.5 text-sm font-normal text-white shadow-sm transition-colors hover:bg-brand-600"
        >
          {t("finance.quickSend.sendMoney")}
        </button>
      </form>
    </div>
  );
}