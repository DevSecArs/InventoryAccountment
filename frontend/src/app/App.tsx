import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";

import { AppShell } from "../layouts/AppShell";
import { MaterialPage } from "../features/catalogs/MaterialPage";
import { SupplierPage } from "../features/catalogs/SupplierPage";
import { UnitPage } from "../features/catalogs/UnitPage";
import { DashboardPage } from "../pages/DashboardPage";
import { NotFoundPage } from "../pages/NotFoundPage";
import { PlannedFeaturePage } from "../pages/PlannedFeaturePage";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      staleTime: 30_000,
      refetchOnWindowFocus: false,
    },
  },
});

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route element={<AppShell />}>
            <Route index element={<DashboardPage />} />
            <Route path="units" element={<UnitPage />} />
            <Route path="materials" element={<MaterialPage />} />
            <Route path="suppliers" element={<SupplierPage />} />
            <Route path="receipts" element={<PlannedFeaturePage feature="Поступления" />} />
            <Route path="reports" element={<PlannedFeaturePage feature="Отчёты" />} />
            <Route path="admin" element={<PlannedFeaturePage feature="Администрирование" />} />
            <Route path="404" element={<NotFoundPage />} />
            <Route path="*" element={<Navigate to="/404" replace />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
