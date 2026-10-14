import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { useAuth } from "../auth.jsx";

export default function Layout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  function handleLogout() {
    logout();
    navigate("/login", { replace: true });
  }

  return (
    <>
      <header className="header">
        <strong>Plate Scan</strong>
        <nav>
          {user.role === "admin" ? (
            <NavLink to="/admin">Admin</NavLink>
          ) : (
            <>
              <NavLink to="/cases" end>
                My Cases
              </NavLink>
              <NavLink to="/claimable">Claimable Cases</NavLink>
            </>
          )}
        </nav>
        <span className="who">
          {user.username} · {user.tenant_name ?? "Platform admin"}
        </span>
        <button onClick={handleLogout}>Log out</button>
      </header>
      <main>
        <Outlet />
      </main>
    </>
  );
}
