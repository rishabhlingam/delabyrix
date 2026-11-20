/**
 * i18n.ts — UI chrome localization for EN / ES / HI.
 * Provides LocaleContext, LocaleProvider, and useLocale() hook with localStorage persistence.
 */
import React, { createContext, useContext, useState } from "react";

export type Locale = "en" | "es" | "hi";

export const TRANSLATIONS: Record<Locale, Record<string, string>> = {
  en: {
    "nav.home": "Home",
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
    "action.sync_bulletins": "Sync Bulletins",
    "action.sync_submit": "Sync Registry",
    "page.patient_title": "Patient & Document Assistant",
    "page.patient_desc": "Ask a clinical question or upload a consent form / hospital bill for analysis.",
    "page.provider_title": "Provider Support",
    "page.provider_desc": "Culturally framed clinical guidance for healthcare providers.",
    "page.hitl_title": "HITL Clinical Review Queue",
    "page.hitl_desc": "Review and approve escalated patient queries before they are released.",
    "page.registry_title": "Cross-Border Registry Explorer",
    "page.registry_desc": "Check medication regulatory status across US FDA and EU EMA.",
    "page.analytics_title": "Analytics Dashboard",
    "page.analytics_desc": "Zero-PII aggregated metrics for care coordination teams.",
  },
  es: {
    "nav.home": "Inicio",
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
    "action.sync_bulletins": "Sincronizar Boletines",
    "action.sync_submit": "Sincronizar Registro",
    "page.patient_title": "Asistente del Paciente",
    "page.patient_desc": "Haga una pregunta clínica o cargue un formulario de consentimiento / factura hospitalaria para análisis.",
    "page.provider_title": "Soporte al Proveedor",
    "page.provider_desc": "Orientación clínica con encuadre cultural para profesionales de la salud.",
    "page.hitl_title": "Cola de Revisión Clínica HITL",
    "page.hitl_desc": "Revise y apruebe consultas de pacientes escaladas antes de su publicación.",
    "page.registry_title": "Explorador de Registros Transfronterizos",
    "page.registry_desc": "Verifique el estado regulatorio de medicamentos en FDA y EMA.",
    "page.analytics_title": "Panel de Análisis",
    "page.analytics_desc": "Métricas agregadas sin PII para equipos de coordinación de atención.",
  },
  hi: {
    "nav.home": "होम",
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
    "action.sync_bulletins": "बुलेटिन सिंक करें",
    "action.sync_submit": "रजिस्ट्री सिंक करें",
    "page.patient_title": "रोगी और दस्तावेज़ सहायक",
    "page.patient_desc": "नैदानिक प्रश्न पूछें या सहमति फॉर्म / अस्पताल बिल विश्लेषण के लिए अपलोड करें।",
    "page.provider_title": "प्रदाता समर्थन",
    "page.provider_desc": "स्वास्थ्य सेवा प्रदाताओं के लिए सांस्कृतिक रूप से तैयार नैदानिक मार्गदर्शन।",
    "page.hitl_title": "HITL नैदानिक समीक्षा कतार",
    "page.hitl_desc": "रोगी प्रश्नों को जारी करने से पहले समीक्षा और अनुमोदित करें।",
    "page.registry_title": "क्रॉस-बॉर्डर रजिस्ट्री एक्सप्लोरर",
    "page.registry_desc": "US FDA और EU EMA में दवाओं की नियामक स्थिति जांचें।",
    "page.analytics_title": "विश्लेषण डैशबोर्ड",
    "page.analytics_desc": "देखभाल समन्वय टीमों के लिए शून्य-PII समग्र मेट्रिक्स।",
  },
};

interface LocaleContextValue {
  locale: Locale;
  setLocale: (l: Locale) => void;
  t: (key: string) => string;
}

const LocaleContext = createContext<LocaleContextValue>({
  locale: "en",
  setLocale: () => {},
  t: (key) => TRANSLATIONS.en[key] ?? key,
});

export function LocaleProvider({ children }: { children: React.ReactNode }) {
  const [locale, setLocaleState] = useState<Locale>(() => {
    const stored = localStorage.getItem("delabyrix_locale");
    return (stored as Locale) || "en";
  });

  function setLocale(l: Locale) {
    localStorage.setItem("delabyrix_locale", l);
    setLocaleState(l);
  }

  const t = (key: string) =>
    TRANSLATIONS[locale][key] ?? TRANSLATIONS.en[key] ?? key;

  return React.createElement(
    LocaleContext.Provider,
    { value: { locale, setLocale, t } },
    children
  );
}

export function useLocale() {
  return useContext(LocaleContext);
}
