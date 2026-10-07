import i18n from "i18next";
import { initReactI18next } from "react-i18next";

import enCommon from "../locales/en/common.json";
import arCommon from "../locales/ar/common.json";
import esCommon from "../locales/es/common.json";
import deCommon from "../locales/de/common.json";

export const resources = {
  en: {
    common: enCommon,
  },
  ar: {
    common: arCommon,
  },
  es: {
    common: esCommon,
  },
  de: {
    common: deCommon,
  },
} as const;

export const defaultNS = "common";
export const fallbackLng = "en";

const savedLng = typeof window !== "undefined" ? localStorage.getItem("i18nextLng") || localStorage.getItem("language") : null;
const browserLng = typeof window !== "undefined" ? navigator.language.split("-")[0] : fallbackLng;
const initialLng = savedLng || (resources[browserLng as keyof typeof resources] ? browserLng : fallbackLng);

i18n
  .use(initReactI18next)
  .init({
    resources,
    lng: initialLng,
    fallbackLng,
    defaultNS,
    ns: ["common"],
    interpolation: {
      escapeValue: false, // React already escapes values
      prefix: "{",
      suffix: "}",
    },
  });

export default i18n;
