import { useCallback, useEffect, useState } from "react";
import { createCamera, createStaffUser, createTenant, listCameras, listTenants, listUsers } from "../api.js";
import { formatDate } from "../format.js";

const EMPTY_USER = { username: "", password: "", tenant_id: "" };
const EMPTY_CAMERA = { id: "", label: "", tenant_id: "" };

function TenantSelect({ tenants, value, onChange }) {
  return (
    <select value={value} onChange={(e) => onChange(e.target.value)} required>
      <option value="">Tenant…</option>
      {tenants.map((t) => (
        <option key={t.id} value={t.id}>
          {t.name}
        </option>
      ))}
    </select>
  );
}

export default function AdminPage() {
  const [tenants, setTenants] = useState([]);
  const [users, setUsers] = useState([]);
  const [cameras, setCameras] = useState([]);
  const [tenantName, setTenantName] = useState("");
  const [newUser, setNewUser] = useState(EMPTY_USER);
  const [newCamera, setNewCamera] = useState(EMPTY_CAMERA);
  const [message, setMessage] = useState(null); // { type: "success" | "error", text }

  const refresh = useCallback(async () => {
    try {
      const [t, u, c] = await Promise.all([listTenants(), listUsers(), listCameras()]);
      setTenants(t);
      setUsers(u);
      setCameras(c);
    } catch (err) {
      setMessage({ type: "error", text: err.message });
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  // Runs a create call, shows the outcome, and reloads every list (counts change too).
  async function submit(event, action, successText, reset) {
    event.preventDefault();
    setMessage(null);
    try {
      await action();
      setMessage({ type: "success", text: successText });
      reset();
      await refresh();
    } catch (err) {
      setMessage({ type: "error", text: err.message });
    }
  }

  return (
    <section>
      <h2>Platform admin</h2>
      {message && <p className={message.type}>{message.text}</p>}

      <h3>Tenants</h3>
      <form
        className="inline-form"
        onSubmit={(e) =>
          submit(e, () => createTenant(tenantName), `Tenant "${tenantName.trim()}" created.`, () => setTenantName(""))
        }
      >
        <input placeholder="Agency name" value={tenantName} onChange={(e) => setTenantName(e.target.value)} required />
        <button type="submit">Create tenant</button>
      </form>
      <table>
        <thead>
          <tr>
            <th>Name</th>
            <th>Users</th>
            <th>Cameras</th>
            <th>Created</th>
          </tr>
        </thead>
        <tbody>
          {tenants.map((t) => (
            <tr key={t.id}>
              <td>{t.name}</td>
              <td>{t.user_count}</td>
              <td>{t.camera_count}</td>
              <td>{formatDate(t.created_at)}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <h3>Staff users</h3>
      <form
        className="inline-form"
        onSubmit={(e) =>
          submit(
            e,
            () => createStaffUser({ ...newUser, tenant_id: Number(newUser.tenant_id) }),
            `Staff user "${newUser.username.trim()}" created.`,
            () => setNewUser(EMPTY_USER),
          )
        }
      >
        <input
          placeholder="Username"
          value={newUser.username}
          onChange={(e) => setNewUser({ ...newUser, username: e.target.value })}
          autoComplete="off"
          required
        />
        <input
          type="password"
          placeholder="Password (min 8)"
          value={newUser.password}
          onChange={(e) => setNewUser({ ...newUser, password: e.target.value })}
          autoComplete="new-password"
          minLength={8}
          required
        />
        <TenantSelect tenants={tenants} value={newUser.tenant_id} onChange={(v) => setNewUser({ ...newUser, tenant_id: v })} />
        <button type="submit">Create staff user</button>
      </form>
      <table>
        <thead>
          <tr>
            <th>Username</th>
            <th>Tenant</th>
            <th>Active</th>
            <th>Created</th>
          </tr>
        </thead>
        <tbody>
          {users.map((u) => (
            <tr key={u.id}>
              <td>{u.username}</td>
              <td>{u.tenant_name ?? "—"}</td>
              <td>{u.is_active ? "yes" : "no"}</td>
              <td>{formatDate(u.created_at)}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <h3>Cameras</h3>
      <form
        className="inline-form"
        onSubmit={(e) =>
          submit(
            e,
            () => createCamera({ ...newCamera, tenant_id: Number(newCamera.tenant_id) }),
            `Camera "${newCamera.id.trim()}" registered.`,
            () => setNewCamera(EMPTY_CAMERA),
          )
        }
      >
        <input
          placeholder="Camera id, e.g. cam_3001"
          value={newCamera.id}
          onChange={(e) => setNewCamera({ ...newCamera, id: e.target.value })}
          required
        />
        <input
          placeholder="Label, e.g. Truck 3"
          value={newCamera.label}
          onChange={(e) => setNewCamera({ ...newCamera, label: e.target.value })}
          required
        />
        <TenantSelect
          tenants={tenants}
          value={newCamera.tenant_id}
          onChange={(v) => setNewCamera({ ...newCamera, tenant_id: v })}
        />
        <button type="submit">Register camera</button>
      </form>
      <table>
        <thead>
          <tr>
            <th>Camera id</th>
            <th>Label</th>
            <th>Tenant</th>
            <th>Active</th>
          </tr>
        </thead>
        <tbody>
          {cameras.map((c) => (
            <tr key={c.id}>
              <td className="mono">{c.id}</td>
              <td>{c.label}</td>
              <td>{c.tenant_name}</td>
              <td>{c.is_active ? "yes" : "no"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
