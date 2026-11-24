import { matchesContext } from '../api/analysis.js'
import { reportStages } from './reportEvidence.js'

function storageKey({ dataset_id, dataset_version, observed_until }) {
  return 'fcore:paper-report:v1:' + JSON.stringify([dataset_id, dataset_version, observed_until])
}

export function readPaperReport(context) {
  try {
    const state = JSON.parse(window.localStorage.getItem(storageKey(context)))
    if (!state || !state.slots || typeof state.question !== 'string' || !Array.isArray(state.turns)) return null
    for (const [stage, slot] of Object.entries(state.slots)) {
      if (!Object.hasOwn(reportStages, stage) || !matchesContext(slot?.reference, context)) return null
    }
    if (state.report && (typeof state.report.content !== 'string' ||
      Object.keys(state.slots).length === 0)) return null
    if (state.turns.some(turn => !state.report || typeof turn?.question !== 'string' || typeof turn.answer !== 'string')) return null
    return state
  } catch {
    return null
  }
}

export function writePaperReport(context, state) {
  try {
    window.localStorage.setItem(storageKey(context), JSON.stringify(state))
  } catch {
    // The live conversation is still usable when browser storage is unavailable.
  }
}
