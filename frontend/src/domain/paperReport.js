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
    // Earlier paper sessions stored model replies with a per-report node ID map.
    const labels = state.report?.node_labels
    if (labels) {
      const originalIds = text => text.replace(/\bN\d{3,}\b/g, label => labels[label] ?? label)
      state.report.content = originalIds(state.report.content)
      if (state.report.thinking) state.report.thinking = originalIds(state.report.thinking)
      for (const turn of state.turns) {
        turn.answer = originalIds(turn.answer)
        if (turn.thinking) turn.thinking = originalIds(turn.thinking)
      }
      delete state.report.node_labels
    }
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
