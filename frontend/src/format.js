export const formatDate = (iso) => (iso ? new Date(iso).toLocaleString() : "—");

export const STATUS_LABELS = {
  pending_claim: "Pending claim",
  active: "Active",
  closed: "Closed",
};

export const osmLink = (lat, lon) =>
  `https://www.openstreetmap.org/?mlat=${lat}&mlon=${lon}#map=16/${lat}/${lon}`;
