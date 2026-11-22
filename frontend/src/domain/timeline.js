// Shared index and identifier convention for the demo's fixed timeline.
export const HISTORY_LENGTH = 11
export const PRESENT_INDEX = HISTORY_LENGTH
export const FUTURE_INDEX = PRESENT_INDEX + 1

export function snapshotId(index) {
  return `S${String(index + 1).padStart(2, '0')}`
}

export function snapshotIndex(id) {
  return Number(id.slice(1)) - 1
}

export const PRESENT_SNAPSHOT_ID = snapshotId(PRESENT_INDEX)
export const LAST_HISTORICAL_SNAPSHOT_ID = snapshotId(PRESENT_INDEX - 1)
