// Stream an undirected CSR graph to the upstream Parallel-KCore solver.
#include <cstdio>
#include <iostream>
#include <limits>

#include "KCore/kcore.h"

int main() {
  std::ios::sync_with_stdio(false);
  std::cin.tie(nullptr);

  Graph<> graph;
  if (!(std::cin >> graph.n >> graph.m) ||
      graph.n > std::numeric_limits<Graph<>::NodeId>::max()) {
    std::cerr << "Invalid CSR graph dimensions\n";
    return 2;
  }
  graph.symmetrized = true;
  graph.weighted = false;
  graph.offsets = parlay::sequence<Graph<>::EdgeId>(graph.n + 1);
  graph.edges = parlay::sequence<Graph<>::Edge>(graph.m);

  Graph<>::EdgeId previous = 0;
  for (auto& offset : graph.offsets) {
    if (!(std::cin >> offset) || offset < previous || offset > graph.m) {
      std::cerr << "Invalid CSR offsets\n";
      return 2;
    }
    previous = offset;
  }
  if (graph.offsets[0] != 0 || graph.offsets[graph.n] != graph.m) {
    std::cerr << "Invalid CSR offset bounds\n";
    return 2;
  }
  for (auto& edge : graph.edges) {
    if (!(std::cin >> edge.v) || edge.v >= graph.n) {
      std::cerr << "Invalid CSR neighbor\n";
      return 2;
    }
  }

  // The upstream divides by the vertex count, and edgeless graphs need no peeling.
  const auto numbers = graph.m == 0
      ? parlay::sequence<Graph<>::NodeId>(graph.n, 0)
      : KCore(graph).kcore();

  // The solver emits benchmark diagnostics in addition to returning the coreness.
  std::fflush(stdout);
  std::cout << "KCORE_RESULT ";
  for (const auto number : numbers) {
    std::cout << number << ' ';
  }
  std::cout << '\n';
}
