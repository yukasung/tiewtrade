import { useLanguage } from "@/context/LanguageContext";
import { useTranslation } from "react-i18next";
import { Navigation } from "swiper/modules";
import { Swiper, SwiperSlide } from "swiper/react";

const trendingStocksData = [
  {
    symbol: "TSLA",
    companyName: "Tesla, Inc",
    price: "$192.53",
    change: "1.01%",
    image: "/images/brand/brand-09.svg",
  },
  {
    symbol: "AAPL",
    companyName: "Apple, Inc",
    price: "$192.53",
    change: "3.59%",
    image: "/images/brand/brand-07.svg",
  },
  {
    symbol: "SPOT",
    companyName: "Spotify, Inc",
    price: "$192.53",
    change: "1.01%",
    image: "/images/brand/brand-11.svg",
  },
  {
    symbol: "PYPL",
    companyName: "Paypal, Inc",
    price: "$192.53",
    change: "1.01%",
    image: "/images/brand/brand-08.svg",
  },
  {
    symbol: "AMZN",
    companyName: "Amazon, Inc",
    price: "$192.53",
    change: "1.01%",
    image: "/images/brand/brand-10.svg",
  },
];

export default function TrendingStocks() {
  const { t } = useTranslation();
  const { dir } = useLanguage();

  const swiperOptions = {
    modules: [Navigation],
    slidesPerView: 1,
    loop: false,
    spaceBetween: 20,
    navigation: {
      nextEl: ".swiper-button-next",
      prevEl: ".swiper-button-prev",
    },
    breakpoints: {
      768: {
        slidesPerView: 2,
      },
      1280: {
        slidesPerView: 2.3,
      },
      1536: {
        slidesPerView: 2.3,
      },
    },
  };
  return (
    <div className="rounded-2xl border border-gray-200 bg-white p-5 sm:p-6 dark:border-gray-800 dark:bg-white/3">
      <div className="mb-6 flex justify-between">
        <h3 className="text-lg font-semibold text-gray-800 dark:text-white/90">
          {t("stocks.trendingStocks.title")}
        </h3>

        <div className="stocks-slider-outer relative flex items-center gap-1.5">
          <div className="swiper-button-prev">
            <svg
              className="rtl:rotate-180"
              width="16"
              height="16"
              viewBox="0 0 16 16"
              fill="none"
              xmlns="http://www.w3.org/2000/svg"
            >
              <path
                d="M10.1667 4L6 8.16667L10.1667 12.3333"
                stroke="currentColor"
                strokeWidth="1.5"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
          </div>

          <div className="swiper-button-next">
            <svg
              className="rtl:rotate-180"
              width="16"
              height="16"
              viewBox="0 0 16 16"
              fill="none"
              xmlns="http://www.w3.org/2000/svg"
            >
              <path
                d="M5.83333 12.6667L10 8.50002L5.83333 4.33335"
                stroke="currentColor"
                strokeWidth="1.5"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
          </div>
        </div>
      </div>

      <div className="stocksSlider">
        <Swiper key={dir} dir={dir} {...swiperOptions}>
          {trendingStocksData.map((item, index) => (
            <SwiperSlide key={index} className="swiper-slide">
              <div className="rounded-2xl bg-gray-100 p-5 dark:bg-white/3">
                <div className="mb-5 flex items-center justify-between border-b border-gray-200 pb-5 dark:border-gray-800">
                  <div className="flex items-center gap-3">
                    <div className="h-10 w-10">
                      <img src={item.image} alt={item.symbol} />
                    </div>

                    <div>
                      <h3 className="text-base font-semibold text-gray-800 dark:text-white/90">
                        {item.symbol}
                      </h3>
                      <span className="block text-theme-xs text-gray-500 dark:text-gray-400">
                        {item.companyName}
                      </span>
                    </div>
                  </div>

                  <div>
                    <div>
                      <h4 className="mb-1 text-end text-theme-sm font-medium text-gray-700 dark:text-gray-400">
                        {item.price}
                      </h4>
                    </div>

                    <span className="flex items-center justify-end gap-1 text-theme-xs font-medium text-success-600 dark:text-success-500">
                      <svg
                        className="fill-current"
                        width="12"
                        height="12"
                        viewBox="0 0 12 12"
                        fill="none"
                        xmlns="http://www.w3.org/2000/svg"
                      >
                        <path
                          fillRule="evenodd"
                          clipRule="evenodd"
                          d="M5.56462 1.62394C5.70193 1.47073 5.90135 1.37433 6.12329 1.37433C6.1236 1.37433 6.12391 1.37433 6.12422 1.37433C6.31631 1.37416 6.50845 1.44732 6.65505 1.59381L9.65514 4.59181C9.94814 4.8846 9.94831 5.35947 9.65552 5.65247C9.36273 5.94546 8.88785 5.94563 8.59486 5.65284L6.87329 3.93248L6.87329 10.125C6.87329 10.5392 6.53751 10.875 6.12329 10.875C5.70908 10.875 5.37329 10.5392 5.37329 10.125L5.37329 3.93579L3.65516 5.65282C3.36218 5.94562 2.8873 5.94547 2.5945 5.65249C2.3017 5.3595 2.30185 4.88463 2.59484 4.59183L5.56462 1.62394Z"
                          fill=""
                        />
                      </svg>
                      {item.change}
                    </span>
                  </div>
                </div>

                <div className="flex items-center gap-3">
                  <button className="flex w-full items-center justify-center rounded-lg border border-gray-300 bg-white p-3 text-theme-sm font-medium text-gray-700 shadow-theme-xs hover:bg-gray-50 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-400 dark:hover:bg-white/3">
                    {t("stocks.trendingStocks.shortStock")}
                  </button>

                  <button className="flex w-full items-center justify-center rounded-lg bg-brand-500 p-3 text-theme-sm font-medium text-white shadow-theme-xs hover:bg-brand-600">
                    {t("stocks.trendingStocks.buyStock")}
                  </button>
                </div>
              </div>
            </SwiperSlide>
          ))}
        </Swiper>
      </div>
    </div>
  );
}
