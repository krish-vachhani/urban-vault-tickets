import { Navigate, Route, Routes } from "react-router";

import { ProtectedRoute } from "../features/auth/components/ProtectedRoute";
import { LoginPage } from "../features/auth/pages/LoginPage";
import { CreateTicketPage } from "../features/tickets/pages/CreateTicketPage";
import { TicketDetailPage } from "../features/tickets/pages/TicketDetailPage";
import { TicketListPage } from "../features/tickets/pages/TicketListPage";
import { AppLayout } from "../shared/layouts/AppLayout";
import { NotFoundPage } from "./pages/NotFoundPage";

/** Declarative route table (README-frontend-architecture §14). */
export function AppRoutes() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route element={<ProtectedRoute />}>
        <Route element={<AppLayout />}>
          <Route path="/" element={<Navigate to="/tickets" replace />} />
          <Route path="/tickets" element={<TicketListPage />} />
          <Route path="/tickets/new" element={<CreateTicketPage />} />
          <Route path="/tickets/:ticketId" element={<TicketDetailPage />} />
        </Route>
      </Route>
      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  );
}
