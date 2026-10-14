import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { listCases } from "../api.js";
import { formatDate, STATUS_LABELS } from "../format.js";

export default function MyCasesPage() {
  const navigate = useNavigate();
  const [status, setStatus] = useState("");
  const [cases, setCases] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError("");
    listCases(status)
      // The API also returns network-wide pending cases; this page only shows our tenant's.
      .then((data) => !cancelled && setCases(data.filter((c) => c.is_mine)))
      .catch((err) => !cancelled && setError(err.message))
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [status]);

  return (
    <section>
      <h2>My Cases</h2>
      <label>
        Status{" "}
        <select value={status} onChange={(e) => setStatus(e.target.value)}>
          <option value="">All</option>
          <option value="active">Active</option>
          <option value="closed">Closed</option>
        </select>
      </label>

      {error && <p className="error">{error}</p>}
      {loading ? (
        <p>Loading…</p>
      ) : cases.length === 0 ? (
        <p>No cases.</p>
      ) : (
        <table>
          <thead>
            <tr>
              <th>VIN</th>
              <th>Status</th>
              <th>Created</th>
              <th>Claimed</th>
              <th>Scans</th>
            </tr>
          </thead>
          <tbody>
            {cases.map((c) => (
              <tr key={c.id} className="clickable" onClick={() => navigate(`/cases/${c.id}`)}>
                <td className="mono">{c.vin}</td>
                <td><span className={`badge ${c.status}`}>{STATUS_LABELS[c.status]}</span></td>
                <td>{formatDate(c.created_at)}</td>
                <td>{formatDate(c.claimed_at)}</td>
                <td>{c.scan_count}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}
