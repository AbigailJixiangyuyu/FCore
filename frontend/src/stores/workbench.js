import { defineStore } from 'pinia'
import queryDefaults from '../../../config/query-defaults.json'
import { currentAlgorithms, historyAlgorithms } from '../domain/algorithms.js'
import {
  FUTURE_INDEX, LAST_HISTORICAL_SNAPSHOT_ID, PRESENT_INDEX, PRESENT_SNAPSHOT_ID,
  forecastSnapshotId, snapshotId, snapshotIndex,
} from '../domain/timeline.js'

export const DEFAULT_DATASET_ID = 'email-eu-core-dept3'
let nextAnalysisRunId = 0

function historyDefaults(defaults) {
  const window = { start_snapshot_id: snapshotId(0), end_snapshot_id: LAST_HISTORICAL_SNAPSHOT_ID }
  return Object.fromEntries(
    Object.keys(historyAlgorithms).map(pattern => [
      pattern, { ...window, ...defaults[pattern] },
    ]),
  )
}

function currentDefaults(defaults) {
  return {
    parallel: { ...defaults.local_core },
    tccs: { ...defaults.local_core, start_snapshot_id: PRESENT_SNAPSHOT_ID },
    pkmc: {},
  }
}

function queryAccount(account, datasetId) {
  return queryDefaults[datasetId] ? account.trim() : account
}

function initialState(datasetId = DEFAULT_DATASET_ID, suggested) {
  const defaults = queryDefaults[datasetId] || {
    ...queryDefaults[DEFAULT_DATASET_ID],
    temporal_core: { k: 1 },
  }
  const account = suggested?.current_account ?? defaults.local_core.account
  const historyAccount = suggested?.history_account ?? account
  const profile = suggested ? {
    ...defaults,
    local_core: { account, k: suggested.current_k },
    periodic: { ...defaults.periodic, account: historyAccount, k: 1 },
    durable: { ...defaults.durable, account: historyAccount, k: 1 },
    burst: { ...defaults.burst, account: historyAccount },
    future_core: { account: historyAccount, k: 1 },
  } : defaults
  return {
    datasetId,
    timeIndex: PRESENT_INDEX,
    historyStartIndex: 0,
    historyEndIndex: PRESENT_INDEX - 1,
    pattern: Object.keys(historyAlgorithms)[0],
    historyDrafts: historyDefaults(profile),
    historySubmitted: historyDefaults(profile),
    currentAlgorithm: Object.keys(currentAlgorithms)[0],
    currentDrafts: currentDefaults(profile),
    currentSubmitted: currentDefaults(profile),
    analysisRunId: null,
    querySelection: '',
    graphLocation: null,
    historySelection: '',
    currentAnchor: account,
    historyAnchor: historyAccount,
    futureDraft: { ...profile.future_core, threshold: 0.5, horizon: 1 },
    futureSubmitted: { ...profile.future_core, threshold: 0.5, horizon: 1 },
    metric: 'auto',
  }
}

export const useWorkbenchStore = defineStore('workbench', {
  state: initialState,
  getters: {
    anomalyAccount: function (state) {
      const location = state.graphLocation
      return location?.source === 'anomaly' ? location.accountId : ''
    },
    stage: function (state) {
      if (state.timeIndex < PRESENT_INDEX) return 'history'
      if (state.timeIndex === PRESENT_INDEX) return 'present'
      return 'future'
    },
    historyRange: function (state) {
      return {
        start_snapshot_id: snapshotId(state.historyStartIndex),
        end_snapshot_id: snapshotId(state.historyEndIndex),
      }
    },
    historyRangeLabel: function () {
      return `${this.historyRange.start_snapshot_id}—${this.historyRange.end_snapshot_id}`
    },
    historyDraft: function (state) {
      return state.historyDrafts[state.pattern]
    },
    historyUsesAccount: function (state) {
      return 'account' in state.historyDrafts[state.pattern]
    },
    historyDraftParameters: function (state) {
      const parameters = { ...state.historyDrafts[state.pattern] }
      if ('account' in parameters)
        parameters.account = queryAccount(parameters.account, state.datasetId)
      return parameters
    },
    historyParameters: function (state) {
      return {
        pattern: state.pattern,
        ...state.historySubmitted[state.pattern],
      }
    },
    hasPendingHistoryParameters: function (state) {
      return (
        JSON.stringify(this.historyDraftParameters) !==
        JSON.stringify(state.historySubmitted[state.pattern])
      )
    },
    historySearchLength: function () {
      const { start_snapshot_id: start, end_snapshot_id: end } = this.historyDraft
      return snapshotIndex(end) - snapshotIndex(start) + 1
    },
    validHistoryParameters: function (state) {
      const parameters = this.historyDraftParameters
      if ('account' in parameters && !parameters.account.trim()) return false
      if (state.pattern === 'burst')
        return (
          Number.isInteger(parameters.l) &&
          parameters.l >= 2 &&
          parameters.l <= this.historySearchLength &&
          Number.isFinite(parameters.delta) &&
          parameters.delta > 0
        )
      if (!Number.isInteger(parameters.k) || parameters.k < 1) return false
      if (state.pattern === 'frequency')
        return (
          Number.isInteger(parameters.t) &&
          parameters.t >= 1 &&
          parameters.t <= this.historySearchLength &&
          Number.isFinite(parameters.f) &&
          parameters.f >= 0 &&
          parameters.f <= 1
        )
      return (
        state.pattern !== 'periodic' ||
        (Number.isFinite(parameters.epsilon) &&
          parameters.epsilon >= 0 &&
          parameters.epsilon <= 1)
      )
    },
    draft: function (state) {
      return state.currentDrafts[state.currentAlgorithm]
    },
    submitted: function (state) {
      return state.currentSubmitted[state.currentAlgorithm]
    },
    draftParameters: function () {
      const parameters = { ...this.draft }
      if ('account' in parameters)
        parameters.account = queryAccount(parameters.account, this.datasetId)
      return parameters
    },
    currentParameters: function (state) {
      if (state.currentAlgorithm === 'pkmc')
        return { snapshot_id: PRESENT_SNAPSHOT_ID, algorithm: 'pkmc' }
      if (state.currentAlgorithm === 'tccs')
        return { ...this.submitted, algorithm: 'tccs' }
      return this.submitted
    },
    currentWindowLabel: function () {
      const start = this.submitted.start_snapshot_id
      return start ? `${start}—${PRESENT_SNAPSHOT_ID}` : ''
    },
    hasPendingParameters: function () {
      return (
        JSON.stringify(this.draftParameters) !== JSON.stringify(this.submitted)
      )
    },
    futureDraftParameters: function (state) {
      return { ...state.futureDraft, account: queryAccount(state.futureDraft.account, state.datasetId) }
    },
    futureSnapshotId: function (state) {
      return forecastSnapshotId(state.futureSubmitted.horizon)
    },
    futureParameters: function (state) {
      return {
        ...state.futureSubmitted,
        threshold: state.futureDraft.threshold,
      }
    },
    validFutureParameters: function () {
      const { account, k } = this.futureDraftParameters
      return !!account.trim() && Number.isInteger(k) && k >= 0 && k <= 10000
    },
    hasPendingFutureParameters: function (state) {
      const { account, k, threshold, horizon } = this.futureDraftParameters
      return account !== state.futureSubmitted.account ||
        k !== state.futureSubmitted.k ||
        horizon !== state.futureSubmitted.horizon ||
        (!state.analysisRunId && threshold !== state.futureSubmitted.threshold)
    },
  },
  actions: {
    clearAnalysis: function () {
      this.analysisRunId = null
      this.querySelection = ''
      this.historySelection = ''
      this.graphLocation = null
    },
    beginAnalysis: function () {
      this.clearAnalysis()
      this.analysisRunId = ++nextAnalysisRunId
    },
    selectAlgorithm: function (field, algorithm) {
      if (this[field] === algorithm) return
      this.clearAnalysis()
      this[field] = algorithm
    },
    selectDataset: function (datasetId, suggested) {
      this.$patch(initialState(datasetId, suggested))
    },
    selectTime: function (index) {
      const timeIndex = Math.max(0, Math.min(FUTURE_INDEX, Math.round(index)))
      if (timeIndex < PRESENT_INDEX) {
        this.selectHistoryRange(this.historyStartIndex, timeIndex)
      } else {
        if (timeIndex !== this.timeIndex) this.clearAnalysis()
        this.timeIndex = timeIndex
      }
    },
    selectHistoryRange: function (start, end) {
      const historyEndIndex = Math.max(0, Math.min(PRESENT_INDEX - 1, Math.round(end)))
      const historyStartIndex = Math.max(0, Math.min(historyEndIndex, Math.round(start)))
      if (this.stage !== 'history') this.clearAnalysis()
      if (this.pattern === 'temporal_core' && (
        historyStartIndex !== this.historyStartIndex || historyEndIndex !== this.historyEndIndex
      )) this.historySelection = ''
      this.$patch({ historyStartIndex, historyEndIndex, timeIndex: historyEndIndex })
    },
    commitQuery: function () {
      this.currentSubmitted[this.currentAlgorithm] = this.draftParameters
      this.beginAnalysis()
    },
    commitHistory: function () {
      const parameters = this.historyDraftParameters
      this.historySubmitted[this.pattern] = parameters
      this.selectHistoryRange(
        snapshotIndex(parameters.start_snapshot_id),
        snapshotIndex(parameters.end_snapshot_id),
      )
      this.beginAnalysis()
    },
    resetHistoryDraft: function () {
      this.historyDrafts[this.pattern] = { ...this.historySubmitted[this.pattern] }
    },
    resetQueryDraft: function () {
      this.currentDrafts[this.currentAlgorithm] = { ...this.submitted }
    },
    commitFuture: function () {
      this.futureSubmitted = this.futureDraftParameters
      this.beginAnalysis()
    },
    resetFutureDraft: function () {
      this.futureDraft = { ...this.futureSubmitted }
    },
    selectCurrent: function (structure, { explicit = true } = {}) {
      this.querySelection = structure.membership_hash
      if (explicit) this.graphLocation = null
      if (!structure.members.includes(this.currentAnchor))
        this.currentAnchor = structure.members[0] || ''
    },
    focusAccount: function (account) {
      this.graphLocation = null
      if (this.stage === 'history') {
        this.historyAnchor = account
        if (this.historyUsesAccount)
          this.historyDrafts[this.pattern].account = account
      } else if (this.stage === 'future') this.futureDraft.account = account
      else {
        this.currentAnchor = account
        if ('account' in this.draft) this.draft.account = account
      }
    },
  },
})
