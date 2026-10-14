import { Navigate, Route, Routes } from "react-router-dom";
import { homeFor, RequireAuth, useAuth } from "./auth.jsx";
import Layout from "./components/Layout.jsx";
import AdminPage from "./pages/AdminPage.jsx";
import CaseDetailPage from "./pages/CaseDetailPage.jsx";
import ClaimablePage from "./pages/ClaimablePage.jsx";
import LoginPage from "./pages/LoginPage.jsx";
import MyCasesPage from "./pages/MyCasesPage.jsx";

export default function App() {
  const { user } = useAuth();

  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        element={
          <RequireAuth>
            <Layout />
          </RequireAuth>
        }
      >
        <Route path="/cases" element={<RequireAuth role="staff"><MyCasesPage /></RequireAuth>} />
        <Route path="/cases/:caseId" element={<RequireAuth role="staff"><CaseDetailPage /></RequireAuth>} />
        <Route path="/claimable" element={<RequireAuth role="staff"><ClaimablePage /></RequireAuth>} />
        <Route path="/admin" element={<RequireAuth role="admin"><AdminPage /></RequireAuth>} />
      </Route>
      <Route path="*" element={<Navigate to={user ? homeFor(user) : "/login"} replace />} />
    </Routes>
  );
}
