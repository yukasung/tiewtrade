import { createInstance } from "i18next";
export const accountI18n = createInstance();
void accountI18n.init({
  lng: "th",
  fallbackLng: "th",
  initAsync: false,
  resources: {
    th: {
      translation: {
        account: "บัญชี",
        menu: "เปิดเมนูบัญชี",
        close: "ปิดเมนูบัญชี",
        navigation: "จัดการบัญชี",
        keys: "API key",
        trading: "บัญชีเทรด",
        security: "TOTP / 2FA",
        prices: "ราคาสด",
        "supported-symbols": "คู่เทรดที่รองรับ",
        home: "หน้าหลัก",
        breadcrumb: "เส้นทางหน้า",
        darkTheme: "เปลี่ยนเป็นโหมดมืด",
        lightTheme: "เปลี่ยนเป็นโหมดสว่าง",
      },
    },
    en: { translation: { account: "Account", menu: "Open account menu", close: "Close account menu",
      navigation: "Account navigation", keys: "API keys", trading: "Trading account", security: "TOTP / 2FA",
      prices: "Live prices", home: "Home", breadcrumb: "Breadcrumb", darkTheme: "Switch to dark mode",
      "supported-symbols": "Supported symbols",
      lightTheme: "Switch to light mode" } },
  },
  interpolation: { escapeValue: false },
});
export const accountText = accountI18n.t.bind(accountI18n);
