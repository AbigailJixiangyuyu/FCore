export const historyAlgorithms = {
  periodic: {
    name: 'TD',
    topic: 'Local Periodic Community',
    paperTitle: 'Periodic Community Search in Temporal Graphs: Time Series-based Methods',
  },
  durable: {
    name: 'ONCE',
    topic: 'Temporal Durable Community',
    paperTitle: 'Effective Durable Community Search in Large Temporal Graph',
  },
  burst: {
    name: 'MBC-B',
    topic: 'Maximal Bursting Core',
    paperTitle: 'Mining Bursting Core in Large Temporal Graphs',
  },
  frequency: {
    name: 'OL',
    topic: 'Frequency-Aware k-Core',
    paperTitle: 'Efficient Frequency-Aware k-Core Query on Temporal Graphs',
  },
  temporal_core: {
    name: 'OTCD',
    topic: 'Time-Range k-Core',
    paperTitle: 'Scalable Time-Range k-Core Query on Temporal Graphs',
  },
}

export const currentAlgorithms = {
  parallel: {
    name: 'Parallel k-Core Decomposition',
    paperTitle: 'Parallel k-Core Decomposition: Theory and Practice',
    method: 'sigmod25-parallel-kcore-v1',
    path: '/queries/local-core',
  },
  tccs: {
    name: 'TCCS',
    topic: 'Online Search',
    paperTitle: 'Evolution Forest Index: Towards Optimal Temporal k-Core Component Search via Time-Topology Isomorphic Computation',
    method: 'tccs-online-v1',
    path: '/queries/local-core',
  },
  pkmc: {
    name: 'PKMC',
    topic: 'Maximum k-Core',
    paperTitle: 'Scalable Algorithms for Densest Subgraph Discovery',
    method: 'pkmc-v1',
    path: '/queries/max-core',
  },
}

export const predictionAlgorithms = {
  zebra: {
    name: 'Zebra',
    paperTitle: 'Zebra: When Temporal Graph Neural Networks Meet Temporal Personalized PageRank',
  },
}

export function algorithmLabel({ name, topic }) {
  return topic ? `${name} · ${topic}` : name
}

export function structureAlgorithm({ origin, parameters, method }) {
  if (origin === 'pattern') return historyAlgorithms[parameters?.pattern]
  return currentAlgorithms[parameters?.algorithm] ?? Object.values(currentAlgorithms).find(
    algorithm => algorithm.method === method,
  )
}
