import { useLanguage } from "@/context/LanguageContext";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import type { Swiper as SwiperClass } from "swiper";
import { EffectFade, Pagination } from "swiper/modules";
import { Swiper, SwiperSlide } from "swiper/react";

export default function MyCards() {
  const { t } = useTranslation();
  const { dir } = useLanguage();
  const [swiperRef, setSwiperRef] = useState<SwiperClass | null>(null);
  const [isBeginning, setIsBeginning] = useState(true);
  const [isEnd, setIsEnd] = useState(false);

  const onSwiper = (swiper: SwiperClass) => {
    setSwiperRef(swiper);
    setIsBeginning(swiper.isBeginning);
    setIsEnd(swiper.isEnd);
  };

  const onSlideChange = (swiper: SwiperClass) => {
    setIsBeginning(swiper.isBeginning);
    setIsEnd(swiper.isEnd);
  };

  const handlePrev = () => {
    swiperRef?.slidePrev();
  };

  const handleNext = () => {
    swiperRef?.slideNext();
  };

  return (
    <div className="rounded-2xl border border-gray-200 bg-white p-6 dark:border-gray-800 dark:bg-white/3">
      <div className="mb-6 flex items-center justify-between">
        <h3 className="text-lg font-semibold text-gray-800 dark:text-white/90">
          {t("finance.myCards.title")}
        </h3>
        <button className="flex h-9 items-center justify-center gap-1.5 rounded-lg border border-gray-300 px-2.5 text-sm font-medium text-gray-700 shadow-xs hover:bg-gray-100 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-400 dark:hover:bg-gray-900">
          <svg
            width="20"
            height="20"
            viewBox="0 0 20 20"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
          >
            <path
              d="M5 10.0002H15.0006M10.0002 5V15.0006"
              stroke="currentColor"
              strokeWidth="1.5"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
          {t("finance.myCards.addCard")}
        </button>
      </div>
      {/* Card Slider */}

      <Swiper
        key={dir}
        dir={dir}
        modules={[Pagination, EffectFade]}
        loop={false}
        slidesPerView={1}
        effect="fade"
        spaceBetween={0}
        onSwiper={onSwiper}
        onSlideChange={onSlideChange}
        className="swiper"
      >
        {/* Card 1 */}
        <SwiperSlide>
          <div className="relative flex flex-col gap-7 overflow-hidden rounded-[14px] border border-gray-800 bg-gray-900 p-6 dark:bg-gray-950">
            <img
              src="/images/payment-gateway/card-vector.png"
              alt="Card Design Vector"
              className="absolute end-0 top-0 rtl:-scale-x-100"
            />
            <div className="flex justify-between">
              <div className="flex items-center gap-4">
                <svg
                  width="12"
                  height="18"
                  viewBox="0 0 12 18"
                  fill="none"
                  xmlns="http://www.w3.org/2000/svg"
                >
                  <path
                    d="M6.27887 16.1701C10.2976 12.1513 10.2976 5.63571 6.27887 1.61701L7.89586 0C12.8075 4.91175 12.8075 12.8753 7.89586 17.7871L6.27887 16.1701ZM3.04479 12.9359C5.27749 10.7033 5.27749 7.08352 3.04479 4.85088L4.66177 3.23388C7.78747 6.35954 7.78747 11.4273 4.66177 14.5528L3.04479 12.9359Z"
                    fill="white"
                  />
                  <path
                    d="M0 7.49219C0.681044 8.04224 0.788117 9.70961 0 10.3699L1.57669 11.5741C3.05722 10.0936 3.05722 7.69324 1.57669 6.21274L0 7.49219Z"
                    fill="white"
                  />
                </svg>
                <span className="flex h-6 shrink-0 items-center gap-1 rounded-full bg-success-500/10 px-2 py-0.5 text-xs font-medium text-success-500">
                  Active
                </span>
              </div>
              <div>
                <img
                  src="/images/payment-gateway/mastercard.png"
                  alt="Mastercard Logo"
                />
              </div>
            </div>
            <div>
              <h3 className="text-base font-normal text-white">Musharof Chy</h3>
            </div>
            <div className="flex justify-between gap-5 sm:gap-10">
              <div className="flex-1">
                <p className="text-sm text-white/80">Card Number</p>
                <p className="text-base font-normal text-white">
                  •••• •••• •••• 4983
                </p>
              </div>
              <div>
                <p className="text-sm text-white/80">EXP</p>
                <p className="text-base font-normal text-white">09/29</p>
              </div>
              <div>
                <p className="text-sm text-white/80">CVC</p>
                <p className="text-base font-normal text-white">659</p>
              </div>
            </div>
          </div>
        </SwiperSlide>
        {/* <!-- Card 2 --> */}
        <SwiperSlide>
          <div className="relative flex flex-col gap-7 overflow-hidden rounded-[14px] bg-gray-900 p-6 dark:bg-gray-950">
            <img
              src="/images/payment-gateway/card-vector.png"
              alt="Card Design Vector"
              className="absolute end-0 top-0 rtl:-scale-x-100"
            />
            <div className="flex justify-between">
              <div className="flex items-center gap-4">
                <svg
                  width="12"
                  height="18"
                  viewBox="0 0 12 18"
                  fill="none"
                  xmlns="http://www.w3.org/2000/svg"
                >
                  <path
                    d="M6.27887 16.1701C10.2976 12.1513 10.2976 5.63571 6.27887 1.61701L7.89586 0C12.8075 4.91175 12.8075 12.8753 7.89586 17.7871L6.27887 16.1701ZM3.04479 12.9359C5.27749 10.7033 5.27749 7.08352 3.04479 4.85088L4.66177 3.23388C7.78747 6.35954 7.78747 11.4273 4.66177 14.5528L3.04479 12.9359Z"
                    fill="white"
                  />
                  <path
                    d="M0 7.49219C0.681044 8.04224 0.788117 9.70961 0 10.3699L1.57669 11.5741C3.05722 10.0936 3.05722 7.69324 1.57669 6.21274L0 7.49219Z"
                    fill="white"
                  />
                </svg>
                <span className="flex h-6 shrink-0 items-center gap-1 rounded-full bg-success-500/10 px-2 py-0.5 text-xs font-medium text-success-500">
                  Active
                </span>
              </div>
              <div>
                <img
                  src="/images/payment-gateway/mastercard.png"
                  alt="Mastercard Logo"
                />
              </div>
            </div>
            <div>
              <h3 className="text-base font-normal text-white">John Wick</h3>
            </div>
            <div className="flex justify-between gap-5 sm:gap-10">
              <div className="flex-1">
                <p className="text-sm text-white/80">Card Number</p>
                <p className="text-base font-normal text-white">
                  •••• •••• •••• 1234
                </p>
              </div>
              <div>
                <p className="text-sm text-white/80">EXP</p>
                <p className="text-base font-normal text-white">12/28</p>
              </div>
              <div>
                <p className="text-sm text-white/80">CVC</p>
                <p className="text-base font-normal text-white">123</p>
              </div>
            </div>
          </div>
        </SwiperSlide>
        {/* <!-- Card 3 --> */}
        <SwiperSlide>
          <div className="relative flex flex-col gap-7 overflow-hidden rounded-[14px] bg-gray-900 p-6 dark:bg-gray-950">
            <img
              src="/images/payment-gateway/card-vector.png"
              alt="Card Design Vector"
              className="absolute end-0 top-0 rtl:-scale-x-100"
            />
            <div className="flex justify-between">
              <div className="flex items-center gap-4">
                <svg
                  width="12"
                  height="18"
                  viewBox="0 0 12 18"
                  fill="none"
                  xmlns="http://www.w3.org/2000/svg"
                >
                  <path
                    d="M6.27887 16.1701C10.2976 12.1513 10.2976 5.63571 6.27887 1.61701L7.89586 0C12.8075 4.91175 12.8075 12.8753 7.89586 17.7871L6.27887 16.1701ZM3.04479 12.9359C5.27749 10.7033 5.27749 7.08352 3.04479 4.85088L4.66177 3.23388C7.78747 6.35954 7.78747 11.4273 4.66177 14.5528L3.04479 12.9359Z"
                    fill="white"
                  />
                  <path
                    d="M0 7.49219C0.681044 8.04224 0.788117 9.70961 0 10.3699L1.57669 11.5741C3.05722 10.0936 3.05722 7.69324 1.57669 6.21274L0 7.49219Z"
                    fill="white"
                  />
                </svg>
                <span className="flex h-6 shrink-0 items-center gap-1 rounded-full bg-white/10 px-2 py-0.5 text-xs font-medium text-gray-500 dark:text-white/90">
                  Inactive
                </span>
              </div>
              <div>
                <img
                  src="/images/payment-gateway/mastercard.png"
                  alt="Mastercard Logo"
                />
              </div>
            </div>
            <div>
              <h3 className="text-base font-normal text-white">Adward John</h3>
            </div>
            <div className="flex justify-between gap-5 sm:gap-10">
              <div className="flex-1">
                <p className="text-sm text-white/80">Card Number</p>
                <p className="text-base font-normal text-white">
                  •••• •••• •••• 5678
                </p>
              </div>
              <div>
                <p className="text-sm text-white/80">EXP</p>
                <p className="text-base font-normal text-white">10/27</p>
              </div>
              <div>
                <p className="text-sm text-white/80">CVC</p>
                <p className="text-base font-normal text-white">987</p>
              </div>
            </div>
          </div>
        </SwiperSlide>
      </Swiper>
      <div className="flex items-center justify-between border-b border-dashed border-gray-200 pt-4 pb-6 dark:border-gray-800">
        <h3 className="text-lg font-medium text-gray-800 dark:text-white/90">
          {t("finance.myCards.virtualCard")}
        </h3>
        <div className="flex gap-1.5">
          <button
            id="card-slider-prev"
            onClick={handlePrev}
            disabled={isBeginning}
            className="flex h-8 w-9 items-center justify-center rounded-lg border border-gray-200 text-gray-700 hover:bg-gray-100 disabled:pointer-events-none disabled:opacity-50 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-400 dark:hover:bg-gray-900"
          >
            <svg
              className="rtl:rotate-180"
              width="16"
              height="16"
              viewBox="0 0 16 16"
              fill="none"
              xmlns="http://www.w3.org/2000/svg"
            >
              <path
                d="M9.58464 3.83325L5.41797 7.99992L9.58464 12.1666"
                stroke="currentColor"
                strokeWidth="1.5"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
          </button>
          <button
            id="card-slider-next"
            onClick={handleNext}
            disabled={isEnd}
            className="flex h-8 w-9 items-center justify-center rounded-lg border border-gray-200 text-gray-700 hover:bg-gray-100 disabled:pointer-events-none disabled:opacity-50 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-400 dark:hover:bg-gray-900"
          >
            <svg
              className="rtl:rotate-180"
              width="16"
              height="16"
              viewBox="0 0 16 16"
              fill="none"
              xmlns="http://www.w3.org/2000/svg"
            >
              <path
                d="M5.91797 12.1666L10.0846 7.99992L5.91797 3.83325"
                stroke="currentColor"
                strokeWidth="1.5"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
          </button>
        </div>
      </div>
      <div className="pt-6">
        <p className="mb-2 text-xs text-gray-500 dark:text-gray-400">
          {t("finance.myCards.recentTransactions")}
        </p>
        <ul className="space-y-1">
          <li className="flex justify-between gap-3 py-2">
            <div className="flex items-center gap-3">
              <div className="inline-flex size-10 shrink-0 items-center justify-center rounded-full border border-gray-200 shadow-xs dark:border-gray-800">
                <img
                  src="./images/payment-gateway/payment-1.svg"
                  className="block size-5 dark:hidden"
                  alt="Payment Icon"
                />
                <img
                  src="./images/payment-gateway/payment-1-dark.svg"
                  className="hidden size-5 dark:block"
                  alt="Payment Icon Dark"
                />
              </div>
              <div>
                <h4 className="mb-0.5 text-sm font-medium text-gray-800 dark:text-white/90">
                  {t("finance.myCards.transactions.paymentReceived")}
                </h4>
                <p className="text-xs text-gray-500 dark:text-gray-400">
                  {t("finance.myCards.transactions.cashbackDesc")}
                </p>
              </div>
            </div>
            <div className="flex items-center justify-end gap-3 text-end">
              <div>
                <p className="mb-0.5 text-sm font-medium text-success-600">
                  +$120.00
                </p>
                <p className="text-xs text-gray-500 dark:text-gray-400">
                  Mar 20
                </p>
              </div>
              <div>
                <a href="#">
                  <svg
                    className="rtl:rotate-180"
                    width="16"
                    height="16"
                    viewBox="0 0 16 16"
                    fill="none"
                    xmlns="http://www.w3.org/2000/svg"
                  >
                    <path
                      d="M5.91797 12.1666L10.0846 7.99992L5.91797 3.83325"
                      stroke="#667085"
                      strokeWidth="1.5"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    />
                  </svg>
                </a>
              </div>
            </div>
          </li>
          <li className="flex justify-between gap-3 py-2">
            <div className="flex items-center gap-3">
              <div className="inline-flex size-10 shrink-0 items-center justify-center rounded-full border border-gray-200 shadow-xs dark:border-gray-800">
                <img
                  src="./images/payment-gateway/payment-2.svg"
                  className="size-5"
                  alt="Netflix Icon"
                />
              </div>
              <div>
                <h4 className="mb-0.5 text-sm font-medium text-gray-800 dark:text-white/90">
                  {t("finance.myCards.transactions.netflixSubscription")}
                </h4>
                <p className="text-xs text-gray-500 dark:text-gray-400">
                  {t("finance.myCards.transactions.netflixDesc")}
                </p>
              </div>
            </div>
            <div className="flex items-center justify-end gap-3 text-end">
              <div>
                <p className="mb-0.5 text-sm font-medium text-error-600">
                  -$36.24
                </p>
                <p className="text-xs text-gray-500 dark:text-gray-400">
                  Sep 18
                </p>
              </div>
              <div>
                <a href="#">
                  <svg
                    className="rtl:rotate-180"
                    width="16"
                    height="16"
                    viewBox="0 0 16 16"
                    fill="none"
                    xmlns="http://www.w3.org/2000/svg"
                  >
                    <path
                      d="M5.91797 12.1666L10.0846 7.99992L5.91797 3.83325"
                      stroke="#667085"
                      strokeWidth="1.5"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    />
                  </svg>
                </a>
              </div>
            </div>
          </li>
          <li className="flex justify-between gap-3 py-2">
            <div className="flex items-center gap-3">
              <div className="inline-flex size-10 shrink-0 items-center justify-center rounded-full border border-gray-200 shadow-xs dark:border-gray-800">
                <img
                  src="./images/payment-gateway/payment-3.svg"
                  className="size-5"
                  alt="Payment Icon"
                />
              </div>
              <div>
                <h4 className="mb-0.5 text-sm font-medium text-gray-800 dark:text-white/90">
                  {t("finance.myCards.transactions.moneyReceived")}
                </h4>
                <p className="text-xs text-gray-500 dark:text-gray-400">
                  {t("finance.myCards.transactions.paypalDesc")}
                </p>
              </div>
            </div>
            <div className="flex items-center justify-end gap-3 text-end">
              <div>
                <p className="mb-0.5 text-sm font-medium text-success-600">
                  +$590
                </p>
                <p className="text-xs text-gray-500 dark:text-gray-400">
                  Feb 12
                </p>
              </div>
              <div>
                <a href="#">
                  <svg
                    className="rtl:rotate-180"
                    width="16"
                    height="16"
                    viewBox="0 0 16 16"
                    fill="none"
                    xmlns="http://www.w3.org/2000/svg"
                  >
                    <path
                      d="M5.91797 12.1666L10.0846 7.99992L5.91797 3.83325"
                      stroke="#667085"
                      strokeWidth="1.5"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    />
                  </svg>
                </a>
              </div>
            </div>
          </li>
          <li className="flex justify-between gap-3 py-2">
            <div className="flex items-center gap-3">
              <div className="inline-flex size-10 shrink-0 items-center justify-center rounded-full border border-gray-200 shadow-xs dark:border-gray-800">
                <img
                  src="./images/payment-gateway/payment-4.svg"
                  className="size-5"
                  alt="Google Ads Icon"
                />
              </div>
              <div>
                <h4 className="mb-0.5 text-sm font-medium text-gray-800 dark:text-white/90">
                  {t("finance.myCards.transactions.googleAds")}
                </h4>
                <p className="text-xs text-gray-500 dark:text-gray-400">
                  {t("finance.myCards.transactions.googleAdsDesc")}
                </p>
              </div>
            </div>
            <div className="flex items-center justify-end gap-3 text-end">
              <div>
                <p className="mb-0.5 text-sm font-medium text-success-600">
                  +$236.24
                </p>
                <p className="text-xs text-gray-500 dark:text-gray-400">
                  Jan 28
                </p>
              </div>
              <div>
                <a href="#">
                  <svg
                    className="rtl:rotate-180"
                    width="16"
                    height="16"
                    viewBox="0 0 16 16"
                    fill="none"
                    xmlns="http://www.w3.org/2000/svg"
                  >
                    <path
                      d="M5.91797 12.1666L10.0846 7.99992L5.91797 3.83325"
                      stroke="#667085"
                      strokeWidth="1.5"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    />
                  </svg>
                </a>
              </div>
            </div>
          </li>
          <li className="flex justify-between gap-3 py-2">
            <div className="flex items-center gap-3">
              <div className="inline-flex size-10 shrink-0 items-center justify-center rounded-full border border-gray-200 shadow-xs dark:border-gray-800">
                <img
                  src="./images/payment-gateway/payment-3.svg"
                  className="size-5"
                  alt="Payment Icon"
                />
              </div>
              <div>
                <h4 className="mb-0.5 text-sm font-medium text-gray-800 dark:text-white/90">
                  {t("finance.myCards.transactions.moneyReceived")}
                </h4>
                <p className="text-xs text-gray-500 dark:text-gray-400">
                  {t("finance.myCards.transactions.paypalDesc")}
                </p>
              </div>
            </div>
            <div className="flex items-center justify-end gap-3 text-end">
              <div>
                <p className="mb-0.5 text-sm font-medium text-success-600">
                  +$1,093
                </p>
                <p className="text-xs text-gray-500 dark:text-gray-400">
                  Jan 10
                </p>
              </div>
              <div>
                <a href="#">
                  <svg
                    className="rtl:rotate-180"
                    width="16"
                    height="16"
                    viewBox="0 0 16 16"
                    fill="none"
                    xmlns="http://www.w3.org/2000/svg"
                  >
                    <path
                      d="M5.91797 12.1666L10.0846 7.99992L5.91797 3.83325"
                      stroke="#667085"
                      strokeWidth="1.5"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    />
                  </svg>
                </a>
              </div>
            </div>
          </li>
        </ul>
        <a
          href="#"
          className="mt-3 flex h-11 w-full items-center justify-center rounded-lg border border-gray-200 px-4 py-3 text-sm font-medium text-gray-700 shadow-xs hover:bg-gray-100 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-400 dark:hover:bg-gray-900"
        >
          {t("finance.myCards.seeAllTransactions")}
        </a>
      </div>
    </div>
  );
}
