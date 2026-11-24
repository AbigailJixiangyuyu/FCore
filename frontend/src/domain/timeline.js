export const FORECAST_HORIZONS = [1, 2, 3]

export function snapshotId(index) {
  return `S${String(index + 1).padStart(2, '0')}`
}

export function snapshotIndex(id) {
  return Number(id.slice(1)) - 1
}

export function forecastSnapshotId(observedUntil, horizon) {
  return snapshotId(snapshotIndex(observedUntil) + horizon)
}
