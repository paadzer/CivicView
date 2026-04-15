// Ireland bounds — keep in sync with backend (civicview.serializers)

export const IRELAND_LAT_MIN = 51.4;
export const IRELAND_LAT_MAX = 55.4;
export const IRELAND_LON_MIN = -11.0;
export const IRELAND_LON_MAX = -5.0;

/**
 * @param {string|number} latStr
 * @param {string|number} lonStr
 * @returns {string|null} Error message or null if valid
 */
export function validateIrelandLocation(latStr, lonStr) {
  const numLat = parseFloat(latStr);
  const numLon = parseFloat(lonStr);
  if (Number.isNaN(numLat) || Number.isNaN(numLon)) return null;
  if (numLat < IRELAND_LAT_MIN || numLat > IRELAND_LAT_MAX) {
    return `Latitude must be between ${IRELAND_LAT_MIN} and ${IRELAND_LAT_MAX} (Ireland).`;
  }
  if (numLon < IRELAND_LON_MIN || numLon > IRELAND_LON_MAX) {
    return `Longitude must be between ${IRELAND_LON_MIN} and ${IRELAND_LON_MAX} (Ireland).`;
  }
  return null;
}
