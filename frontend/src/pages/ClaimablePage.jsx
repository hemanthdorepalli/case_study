import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { claimCase, listCases } from "../api.js";
import { formatDate } from "../format.js";

function claimErrorMessage(err) {
  if (err.status === 409) return `Already claimed – ${err.message}`;
  // Another agency claimed it first, so it is no longer visible to us.
  if (err.status === 404) return "This case is no longer available (it may have just been claimed by another agency).";
  return err.message;
}

export default function ClaimablePage() {
  const [cases, setCases] = useState([]);
  const [loading, setLoading] = useState(true);
  const [claiming, setClaiming] = useState(null);
  const [message, setMessage] = useState(null); // { type: "success" | "error", text, caseId? }

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      setCases(await listCases("pending_claim"));
    } catch (err) {
      setMessage({ type: "error", text: err.message });
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  async function handleClaim(caseId) {
    setClaiming(caseId);
    setMessage(null);
    try {
      const claimed = await claimCase(caseId);
      setMessage({ type: "success", text: `Case #${claimed.id} (${claimed.vin}) is now yours.`, caseId: claimed.id });
    } catch (err) {
      setMessage({ type: "error", text: claimErrorMessage(err) });
    } finally {
      setClaiming(null);
      await refresh();
    }
  }

  return (
    <section>
      <h2>Claimable Cases</h2>
      <p className="hint">Pending cases opened by any agency's cameras. The first agency to claim one owns it.</p>
      <button onClick={refresh} disabled={loading}>
        Refresh
      </button>

      {message && (
        <p className={message.type}>
          {message.text} {message.caseId && <Link to={`/cases/${message.caseId}`}>Open case →</Link>}
        </p>
      )}

      {loading ? (
        <p>Loading…</p>
      ) : cases.length === 0 ? (
        <p>No cases waiting to be claimed.</p>
      ) : (
        <table>
          <thead>
            <tr>
              <th>VIN</th>
              <th>Opened</th>
              <th>Seen by our cameras</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {cases.map((c) => (
              <tr key={c.id}>
                <td className="mono">{c.vin}</td>
                <td>{formatDate(c.created_at)}</td>
                <td>{c.scan_count}</td>
                <td>
                  <button onClick={() => handleClaim(c.id)} disabled={claiming !== null}>
                    {claiming === c.id ? "Claiming…" : "Claim"}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}
