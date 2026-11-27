#!/usr/bin/env python3
"""Exactly test the proposition on cycle graphs, exhaustively enumerating sets."""

from collections import deque


def cycle_graph(n):
    """Return a finite undirected graph as a tuple of integer adjacency masks."""
    adjacency = [0] * n
    for vertex in range(n):
        neighbor = (vertex + 1) % n
        adjacency[vertex] |= 1 << neighbor
        adjacency[neighbor] |= 1 << vertex
    return tuple(adjacency)


def verify_simple_undirected_graph(adjacency):
    """Verify the graph representation exactly, including absence of loops."""
    n = len(adjacency)
    if n == 0:
        return False
    allowed = (1 << n) - 1
    for vertex, neighbors in enumerate(adjacency):
        if not isinstance(neighbors, int) or neighbors < 0:
            return False
        if neighbors & ~allowed:
            return False
        if neighbors & (1 << vertex):
            return False
        for other in range(n):
            if bool(neighbors & (1 << other)) != bool(
                adjacency[other] & (1 << vertex)
            ):
                return False
    return True


def all_distances(adjacency):
    """Compute exact shortest-path distances using BFS from every vertex."""
    distances = []
    for source in range(len(adjacency)):
        row = [None] * len(adjacency)
        row[source] = 0
        queue = deque([source])
        while queue:
            vertex = queue.popleft()
            for neighbor in range(len(adjacency)):
                if (
                    adjacency[vertex] & (1 << neighbor)
                    and row[neighbor] is None
                ):
                    row[neighbor] = row[vertex] + 1
                    queue.append(neighbor)
        distances.append(row)
    return distances


def square_from_distances(distances):
    """Construct precisely the graph whose edges have distance one or two."""
    n = len(distances)
    return tuple(
        sum(
            1 << other
            for other in range(n)
            if other != vertex
            and distances[vertex][other] is not None
            and 1 <= distances[vertex][other] <= 2
        )
        for vertex in range(n)
    )


def maximal_independent_sets(adjacency):
    """Exhaustively check every subset for independence and maximality."""
    n = len(adjacency)
    full = (1 << n) - 1
    result = []
    for subset in range(1 << n):
        independent = True
        dominated = subset
        for vertex in range(n):
            if subset & (1 << vertex):
                if adjacency[vertex] & subset:
                    independent = False
                    break
                dominated |= adjacency[vertex]
        # An independent set is maximal exactly when it dominates all vertices.
        if independent and dominated == full:
            result.append(subset)
    return result


def vertices(mask, n):
    return tuple(vertex for vertex in range(n) if mask & (1 << vertex))


def edges(adjacency):
    return [
        (u, v)
        for u in range(len(adjacency))
        for v in range(u + 1, len(adjacency))
        if adjacency[u] & (1 << v)
    ]


def main():
    tested = 0
    enumerated_subsets = 0

    # This bounded systematic search includes C6 and uses exact integers only.
    for n in range(3, 11):
        graph = cycle_graph(n)
        if not verify_simple_undirected_graph(graph):
            raise RuntimeError("Invalid original graph representation.")

        distances = all_distances(graph)
        connected = all(
            distance is not None
            for row in distances
            for distance in row
        )

        square = square_from_distances(distances)
        if not verify_simple_undirected_graph(square):
            raise RuntimeError("Invalid square graph representation.")

        # Independently verify the square's defining adjacency condition.
        for u in range(n):
            for v in range(n):
                expected = (
                    u != v
                    and distances[u][v] is not None
                    and 1 <= distances[u][v] <= 2
                )
                if bool(square[u] & (1 << v)) != expected:
                    raise RuntimeError("Square adjacency verification failed.")

        graph_sets = maximal_independent_sets(graph)
        square_sets = maximal_independent_sets(square)
        graph_sizes = {mask.bit_count() for mask in graph_sets}
        square_sizes = {mask.bit_count() for mask in square_sets}

        full = (1 << n) - 1
        square_complete = all(
            square[vertex] == (full ^ (1 << vertex))
            for vertex in range(n)
        )
        square_well_covered = bool(square_sets) and len(square_sizes) == 1
        graph_well_covered = bool(graph_sets) and len(graph_sizes) == 1

        tested += 1
        enumerated_subsets += 2 * (1 << n)

        if connected and square_well_covered and not square_complete:
            if not graph_well_covered:
                smallest = min(graph_sets, key=int.bit_count)
                largest = max(graph_sets, key=int.bit_count)
                if smallest.bit_count() >= largest.bit_count():
                    raise RuntimeError("Strict conclusion violation absent.")

                missing_square_edge = next(
                    (u, v)
                    for u in range(n)
                    for v in range(u + 1, n)
                    if not (square[u] & (1 << v))
                )

                print("Explicit counterexample: cycle graph C{}".format(n))
                print("Vertex set:", tuple(range(n)))
                print("G edges:", edges(graph))
                print("G^2 edges:", edges(square))
                print("All verification uses exact integer arithmetic.")
                print("Finite, simple, undirected graph: verified.")
                print("Connected: verified by all-pairs BFS.")
                print("Distance-2 square definition: verified for every pair.")
                print("G^2 is not complete; missing edge:", missing_square_edge)
                print("All maximal independent sets of G^2:")
                for subset in square_sets:
                    print(" ", vertices(subset, n), "size =", subset.bit_count())
                print("G^2 is well-covered; common size:", next(iter(square_sizes)))
                print("All maximal independent sets of G:")
                for subset in graph_sets:
                    print(" ", vertices(subset, n), "size =", subset.bit_count())
                print("Two maximal independent sets violating well-coveredness:")
                print(" ", vertices(smallest, n), "size =", smallest.bit_count())
                print(" ", vertices(largest, n), "size =", largest.bit_count())
                print(
                    "Maximality and independence were verified by exhaustive "
                    "enumeration of every vertex subset."
                )
                print("VERDICT: COUNTEREXAMPLE_VERIFIED")
                return

    print(
        "Exactly tested {} cycle graphs and {} subsets across the graphs "
        "and their squares; no valid counterexample found.".format(
            tested, enumerated_subsets
        )
    )
    print("VERDICT: CONSISTENT_NO_COUNTEREXAMPLE")


if __name__ == "__main__":
    main()
