import { Navigate, Route, Routes } from "react-router-dom";

import AppShell from "./components/layout/AppShell";
import Dashboard from "./pages/Dashboard";
import Exceptions from "./pages/Exceptions";
import BreakDetail from "./pages/BreakDetail";
import Ledger from "./pages/Ledger";
import AuditLog from "./pages/AuditLog";

/**
 * Route table.
 *
 * Exceptions is the default landing route rather than the dashboard: the
 * product is a work queue, and a controller opening this app wants the list of
 * things needing a decision, not a summary of things already handled.
 */
export default function App() {
  return (
    <AppShell>
      <Routes>
        <Route path="/" element={<Navigate to="/exceptions" replace />} />
        <Route path="/exceptions" element={<Exceptions />} />
        <Route path="/exceptions/:breakId" element={<BreakDetail />} />
        <Route path="/dashboard" element={<Dashboard />} />
        <Route path="/ledger" element={<Ledger />} />
        <Route path="/audit" element={<AuditLog />} />
        <Route path="*" element={<Navigate to="/exceptions" replace />} />
      </Routes>
    </AppShell>
  );
}
