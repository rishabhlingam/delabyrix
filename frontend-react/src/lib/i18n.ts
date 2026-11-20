/**
 * i18n.ts — UI chrome localization stub.
 *
 * TODO(teammate-4): Implement this module.
 * See LocaleSwitcher.tsx for full requirements.
 */

export type Locale = "en" | "es" | "hi";

// TODO(teammate-4): Expand this with all required translation keys.
export const TRANSLATIONS: Record<Locale, Record<string, string>> = {
  en: {
    "nav.patient_assistant": "Patient Assistant",
    "nav.hitl_review": "HITL Review",
    "nav.registry": "Registry Explorer",
    "nav.provider_support": "Provider Support",
    "nav.analytics": "Analytics",
    "status.pending": "Pending Clinical Review",
    "status.approved": "Approved",
    "status.rejected": "Rejected",
    "action.submit": "Submit Query",
    "action.approve": "Approve Guidance",
    "action.reject": "Reject",
    "action.refresh": "Refresh",
    "action.search": "Search",
    "action.analyze_document": "Analyze Document",
  },
  es: {
    "nav.patient_assistant": "Asistente de Paciente",
    "nav.hitl_review": "Revisión Clínica",
    "nav.registry": "Explorador de Registros",
    "nav.provider_support": "Soporte al Proveedor",
    "nav.analytics": "Análisis",
    "status.pending": "Revisión Clínica Pendiente",
    "status.approved": "Aprobado",
    "status.rejected": "Rechazado",
    "action.submit": "Enviar Consulta",
    "action.approve": "Aprobar Guía",
    "action.reject": "Rechazar",
    "action.refresh": "Actualizar",
    "action.search": "Buscar",
    "action.analyze_document": "Analizar Documento",
  },
  hi: {
    "nav.patient_assistant": "रोगी सहायक",
    "nav.hitl_review": "HITL समीक्षा",
    "nav.registry": "रजिस्ट्री एक्सप्लोरर",
    "nav.provider_support": "प्रदाता समर्थन",
    "nav.analytics": "विश्लेषण",
    "status.pending": "नैदानिक समीक्षा लंबित",
    "status.approved": "अनुमोदित",
    "status.rejected": "अस्वीकृत",
    "action.submit": "प्रश्न भेजें",
    "action.approve": "मार्गदर्शन अनुमोदित करें",
    "action.reject": "अस्वीकार करें",
    "action.refresh": "ताज़ा करें",
    "action.search": "खोजें",
    "action.analyze_document": "दस्तावेज़ विश्लेषण करें",
  },
};

// TODO(teammate-4): Add React context (LocaleContext) and useLocale() hook here.
// Example scaffold:
//
// import React, { createContext, useContext, useState } from "react";
//
// interface LocaleContextValue {
//   locale: Locale;
//   setLocale: (l: Locale) => void;
//   t: (key: string) => string;
// }
//
// const LocaleContext = createContext<LocaleContextValue>({
//   locale: "en",
//   setLocale: () => {},
//   t: (key) => TRANSLATIONS.en[key] ?? key,
// });
//
// export function LocaleProvider({ children }: { children: React.ReactNode }) {
//   const [locale, setLocale] = useState<Locale>("en");
//   const t = (key: string) => TRANSLATIONS[locale][key] ?? TRANSLATIONS.en[key] ?? key;
//   return (
//     <LocaleContext.Provider value={{ locale, setLocale, t }}>
//       {children}
//     </LocaleContext.Provider>
//   );
// }
//
// export function useLocale() {
//   return useContext(LocaleContext);
// }
