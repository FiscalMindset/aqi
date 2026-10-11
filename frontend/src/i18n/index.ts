import i18n from "i18next";
import { initReactI18next } from "react-i18next";
import en from "./en.json";
import hi from "./hi.json";

const STORAGE_KEY = "dhuan.language";

function detectLanguage(): string {
  const stored = localStorage.getItem(STORAGE_KEY);
  if (stored) return stored;
  return navigator.language.startsWith("hi") ? "hi" : "en";
}

i18n.use(initReactI18next).init({
  resources: {
    en: { translation: en },
    hi: { translation: hi },
  },
  lng: detectLanguage(),
  fallbackLng: "en",
  interpolation: { escapeValue: false },
});

i18n.on("languageChanged", (lng) => {
  localStorage.setItem(STORAGE_KEY, lng);
  document.documentElement.lang = lng;
});

// keep <html lang> in sync from the very first render
document.documentElement.lang = i18n.resolvedLanguage ?? "en";

export default i18n;
