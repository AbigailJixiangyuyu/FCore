function largestComponentSize(neighbors) {
  const unseen = new Set(neighbors.keys())
  let largest = 0
  for (const start of neighbors.keys()) {
    if (!unseen.delete(start)) continue
    const members = [start]
    for (let index = 0; index < members.length; index++) {
      for (const neighbor of neighbors.get(members[index])) {
        if (unseen.delete(neighbor)) members.push(neighbor)
      }
    }
    largest = Math.max(largest, members.length)
  }
  return largest
}

export function summarizeGraph({ nodes, edges, stats, core_numbers = {}, snapshot_ids }) {
  const neighbors = new Map(nodes.map(node => [node.id, new Set()]))
  for (const { u, v } of edges) {
    if (u === v) continue
    neighbors.get(u).add(v)
    neighbors.get(v).add(u)
  }

  const degrees = Array.from(neighbors.values(), accounts => accounts.size)
    .sort((a, b) => a - b)
  const size = degrees.length
  const total = degrees.reduce((sum, degree) => sum + degree, 0)
  const lowerMiddle = Math.floor((size - 1) / 2)
  const upperMiddle = Math.floor(size / 2)
  const maxDegree = degrees.at(-1)
  const coreNumbers = Object.values(core_numbers)
  const maxCore = coreNumbers.length
    ? coreNumbers.reduce((maximum, core) => Math.max(maximum, core), 0)
    : null
  const snapshotCount = snapshot_ids?.length || 1

  return {
    nodeCount: size,
    transactionCount: stats.transaction_count,
    edgeCount: edges.length,
    density: stats.density,
    averageDegree: size ? total / size : null,
    medianDegree: size ? (degrees[lowerMiddle] + degrees[upperMiddle]) / 2 : null,
    maxDegree,
    maxDegreeAccounts: nodes.filter(node => neighbors.get(node.id).size === maxDegree)
      .map(node => node.id),
    maxCore,
    maxCoreSize: coreNumbers.filter(core => core === maxCore).length,
    largestComponentSize: largestComponentSize(neighbors),
    averageTransactionsPerSnapshot: snapshotCount > 1 ? stats.transaction_count / snapshotCount : null,
  }
}

function quantile(sorted, fraction) {
  const position = (sorted.length - 1) * fraction
  const lower = Math.floor(position)
  const upper = Math.ceil(position)
  return sorted[lower] + (position - lower) * (sorted[upper] - sorted[lower])
}

function summarizeScoreBox(scores, accounts) {
  const q1 = quantile(scores, 0.25)
  const q3 = quantile(scores, 0.75)
  const reach = 1.5 * (q3 - q1)
  const lowerFence = q1 - reach
  const upperFence = q3 + reach

  return {
    q1,
    q3,
    lowerWhisker: scores.find(score => score >= lowerFence),
    upperWhisker: scores.findLast(score => score <= upperFence),
    minimum: scores[0],
    maximum: scores.at(-1),
    outliers: accounts.filter(({ score }) => score < lowerFence || score > upperFence),
  }
}

export function summarizeRisk(members, accounts, inspectedAccount) {
  const scope = new Set(members)
  const scored = accounts.filter(account => scope.has(account.account_id))
  const scoredIds = new Set(scored.map(account => account.account_id))
  const unscored = members.filter(id => !scoredIds.has(id))
    .map(account_id => ({ account_id, score: null }))
  const scores = scored.map(({ score }) => score).sort((a, b) => a - b)
  const total = scores.reduce((sum, score) => sum + score, 0)

  return {
    memberScores: [...scored, ...unscored],
    scoredCount: scored.length,
    topCount: scored.filter(account => account.rank <= 10).length,
    mean: scores.length ? total / scores.length : null,
    median: scores.length ? quantile(scores, 0.5) : null,
    box: scores.length ? summarizeScoreBox(scores, scored) : null,
    focus: scored.find(account => account.account_id === inspectedAccount) ?? scored[0],
  }
}

