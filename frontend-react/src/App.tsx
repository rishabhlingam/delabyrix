import React from "react";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import AppShell from "@/components/layout/AppShell";
import HomePage from "@/pages/HomePage";
import PatientAssistantPage from "@/pages/PatientAssistantPage";
import HITLReviewPage from "@/pages/HITLReviewPage";
import RegistryExplorerPage from "@/pages/RegistryExplorerPage";
import ProviderSupportPage from "@/pages/ProviderSupportPage";
import AnalyticsDashboardPage from "@/pages/AnalyticsDashboardPage";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<AppShell />}>
          <Route index element={<HomePage />} />
          <Route path="patient" element={<PatientAssistantPage />} />
          <Route path="hitl" element={<HITLReviewPage />} />
          <Route path="registry" element={<RegistryExplorerPage />} />
          <Route path="provider" element={<ProviderSupportPage />} />
          <Route path="analytics" element={<AnalyticsDashboardPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
