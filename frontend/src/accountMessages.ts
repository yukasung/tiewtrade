import { createInstance } from "i18next";
const accountI18n = createInstance();
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
      },
    },
  },
  interpolation: { escapeValue: false },
});
export const accountText = accountI18n.t.bind(accountI18n);
