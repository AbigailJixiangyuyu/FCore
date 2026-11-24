export const historyAlgorithms = {
  historical_core: {
    name: 'PHC-Query',
    topic: 'Historical k-Core Query',
    paperTitle: 'Querying historical K-cores in large temporal graphs',
    resultWindow: 'submitted',
  },
  temporal_core: {
    name: 'OTCD',
    topic: 'Scalable Time-Range k-Core Query',
    paperTitle: 'Scalable Time-Range k-Core Query on Temporal Graphs',
    resultWindow: 'tightest',
  },
  burst: {
    name: 'MBC-B',
    topic: 'Bursting k-Core',
    paperTitle: 'Mining Bursting Core in Large Temporal Graphs',
  },
  periodic: {
    name: 'TD',
    topic: 'Periodic k-Core',
    paperTitle: 'Periodic Community Search in Temporal Graphs: Time Series-based Methods',
  },
  durable: {
    name: 'ONCE',
    topic: 'Durable k-Core',
    paperTitle: 'Effective Durable Community Search in Large Temporal Graph',
  },
  frequency: {
    name: 'OL',
    topic: 'Frequency-Aware k-Core',
    paperTitle: 'Efficient Frequency-Aware k-Core Query on Temporal Graphs',
  },
}

export const currentAlgorithms = {
  tccs: {
    name: 'TCCS',
    topic: 'Temporal k-Core Component Search',
    paperTitle: 'Evolution Forest Index: Towards Optimal Temporal k-Core Component Search via Time-Topology Isomorphic Computation',
    method: 'tccs-online-v1',
    path: '/queries/local-core',
  },
  pkmc: {
    name: 'PKMC',
    topic: 'Maximum-Core Search',
    paperTitle: 'Scalable Algorithms for Densest Subgraph Discovery',
    method: 'pkmc-v1',
    path: '/queries/max-core',
  },
  parallel: {
    name: 'Parallel k-Core Decomposition',
    paperTitle: 'Parallel k-Core Decomposition: Theory and Practice',
    method: 'sigmod25-parallel-kcore-v1',
    path: '/queries/local-core',
  },
}

export const predictionAlgorithms = {
  zebra: {
    name: 'Zebra',
    topic: 'Temporal Link Prediction',
    paperTitle: 'Zebra: When Temporal Graph Neural Networks Meet Temporal Personalized PageRank',
  },
}

export function algorithmLabel({ name, topic }) {
  return topic ?? name
}

export function structureAlgorithm({ origin, parameters, method }) {
  if (origin === 'pattern') return historyAlgorithms[parameters?.pattern]
  return currentAlgorithms[parameters?.algorithm] ?? Object.values(currentAlgorithms).find(
    algorithm => algorithm.method === method,
  )
}
