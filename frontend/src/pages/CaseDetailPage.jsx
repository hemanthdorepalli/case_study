import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { getCase, getTrail } from "../api.js";
import { formatDate, osmLink, STATUS_LABELS } from "../format.js";

export default function CaseDetailPage() {
  const { caseId } = useParams();
  const [caseInfo, setCaseInfo] = useState(null);
  const [trail, setTrail] = useState([]);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    setError("");
    (async () => {
      try {
        const info = await getCase(caseId);
        // Only the owning tenant has a trail; pending cases have none until claimed.
        const scans = info.is_mine ? await getTrail(caseId) : [];
        if (!cancelled) {
          setCaseInfo(info);
          setTrail(scans);
        }
      } catch (err) {
        if (!cancelled) setError(err.status === 404 ? "Case not found." : err.message);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [caseId]);

  if (error) return <p className="error">{error}</p>;
  if (!caseInfo) return <p>Loading…</p>;

  return (
    <section>
      <p>
        <Link to="/cases">← My Cases</Link>
      </p>
      <h2>
        Case #{caseInfo.id} – <span className="mono">{caseInfo.vin}</span>
      </h2>
      <dl className="facts">
        <dt>Status</dt>
        <dd><span className={`badge ${caseInfo.status}`}>{STATUS_LABELS[caseInfo.status]}</span></dd>
        <dt>Created</dt>
        <dd>{formatDate(caseInfo.created_at)}</dd>
        <dt>Claimed</dt>
        <dd>{formatDate(caseInfo.claimed_at)}</dd>
        {caseInfo.closed_at && (
          <>
            <dt>Closed</dt>
            <dd>{formatDate(caseInfo.closed_at)}</dd>
          </>
        )}
      </dl>

      <h3>Location trail</h3>
      {!caseInfo.is_mine ? (
        <p>
          This case hasn't been claimed yet. <Link to="/claimable">Claim it</Link> to see its location trail.
        </p>
      ) : trail.length === 0 ? (
        <p>No sightings yet.</p>
      ) : (
        <table>
          <thead>
            <tr>
              <th>Time</th>
              <th>Lat, Long</th>
              <th>Plate</th>
              <th>Source</th>
              <th>Camera</th>
              <th>Map</th>
            </tr>
          </thead>
          <tbody>
            {trail.map((scan, index) => (
              <tr key={scan.id ?? `network-${index}`}>
                <td>{formatDate(scan.scanned_at)}</td>
                <td className="mono">
                  {scan.latitude.toFixed(5)}, {scan.longitude.toFixed(5)}
                </td>
                <td className="mono">{scan.plate}</td>
                <td>
                  <span className={`badge ${scan.source}`}>{scan.source}</span>
                </td>
                {/* Network sightings never include camera or image details. */}
                <td>{scan.camera_id ?? "—"}</td>
                <td>
                  <a href={osmLink(scan.latitude, scan.longitude)} target="_blank" rel="noreferrer">
                    View on map
                  </a>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}
