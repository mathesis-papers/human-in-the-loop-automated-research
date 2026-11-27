#!/usr/bin/env python3
"""Search exactly for a zero-forcing set of size < 8 in P(7,3)."""

from itertools import combinations


def label(vertex, n):
    return f"u_{vertex}" if vertex < n else f"v_{vertex - n}"


def construct_graph(n):
    assert type(n) is int and n >= 7
    edges = set()

    def add_edge(a, b):
        assert a != b
        edges.add(tuple(sorted((a, b))))

    for i in range(n):
        add_edge(i, (i + 1) % n)
        add_edge(i, n + i)
        add_edge(n + i, n + (i + 3) % n)

    adjacency = [set() for _ in range(2 * n)]
    for a, b in edges:
        adjacency[a].add(b)
        adjacency[b].add(a)
    return edges, adjacency


def verify_graph(n, edges, adjacency):
    """Check all graph-definition hypotheses using exact integer arithmetic."""
    assert type(n) is int and n >= 7
    vertices = set(range(2 * n))
    assert len(adjacency) == 2 * n

    expected_edges = set()
    for i in range(n):
        for a, b in (
            (i, (i + 1) % n),
            (i, n + i),
            (n + i, n + (i + 3) % n),
        ):
            assert a in vertices and b in vertices and a != b
            expected_edges.add(tuple(sorted((a, b))))
    assert edges == expected_edges

    for a in vertices:
        expected_neighbors = {
            b if a == c else c
            for c, b in expected_edges
            if a == c or a == b
        }
        assert adjacency[a] == expected_neighbors
        assert a not in adjacency[a]
        assert len(adjacency[a]) == 3
        for b in adjacency[a]:
            assert a in adjacency[b]

    reached = {0}
    pending = [0]
    while pending:
        a = pending.pop()
        for b in adjacency[a]:
            if b not in reached:
                reached.add(b)
                pending.append(b)
    assert reached == vertices


def bitmask_closure(initial, neighbor_masks, full_mask):
    """Compute exact sequential zero-forcing closure with integer bitmasks."""
    blue = sum(1 << vertex for vertex in initial)
    while blue != full_mask:
        progress = False
        for source, neighbors in enumerate(neighbor_masks):
            if not (blue & (1 << source)):
                continue
            white_neighbors = neighbors & (full_mask ^ blue)
            if white_neighbors and not (white_neighbors & (white_neighbors - 1)):
                blue |= white_neighbors
                progress = True
        if not progress:
            break
    return blue


def independently_verify_witness(initial, adjacency):
    """Recheck each force using sets, independently of the bitmask search."""
    vertices = set(range(len(adjacency)))
    assert len(initial) == len(set(initial))
    assert set(initial) <= vertices
    assert len(initial) < 8

    blue = set(initial)
    trace = []
    while blue != vertices:
        move = None
        for source in sorted(blue):
            white_neighbors = adjacency[source] - blue
            if len(white_neighbors) == 1:
                target = next(iter(white_neighbors))
                move = (source, target)
                break
        if move is None:
            return False, trace

        source, target = move
        assert source in blue
        assert target not in blue
        assert adjacency[source] - blue == {target}
        blue.add(target)
        trace.append(move)

    assert blue == vertices
    assert len(trace) == len(vertices) - len(initial)
    return True, trace


def main():
    n = 7
    edges, adjacency = construct_graph(n)
    verify_graph(n, edges, adjacency)

    neighbor_masks = [
        sum(1 << neighbor for neighbor in neighbors)
        for neighbors in adjacency
    ]
    full_mask = (1 << (2 * n)) - 1
    tested = 0

    # Exhaust increasing sizes: any successful set here proves Z(P(7,3)) < 8.
    for size in range(8):
        for initial in combinations(range(2 * n), size):
            tested += 1
            if bitmask_closure(initial, neighbor_masks, full_mask) != full_mask:
                continue

            verified, trace = independently_verify_witness(initial, adjacency)
            assert verified

            print(f"Counterexample graph: P({n},3)")
            print(f"Verified integer n = {n} >= 7.")
            print(f"Verified all {2*n} vertices and all {len(edges)} prescribed edges.")
            print("Verified simplicity, undirected adjacency, cubic degrees, and connectedness.")
            print("All checks use exact integers and finite sets; no numerical tolerances.")
            print("Edges:")
            for a, b in sorted(edges):
                print(f"  {label(a, n)} -- {label(b, n)}")
            print(
                "Initial blue set:",
                "{" + ", ".join(label(v, n) for v in initial) + "}",
            )
            print(f"Initial blue set size: {size} < 8")
            print("Independently verified forcing sequence:")
            for step, (source, target) in enumerate(trace, 1):
                print(f"  {step}: {label(source, n)} -> {label(target, n)}")
            print("Every force has a blue source with exactly one white neighbor.")
            print(f"All {2*n} vertices become blue.")
            print(f"Sets tested in increasing cardinality: {tested}")
            print(f"Thus Z(P({n},3)) <= {size} < 8, contradicting the proposition.")
            print("VERDICT: COUNTEREXAMPLE_VERIFIED")
            return

    print(
        f"Exhaustively checked {tested} initial sets of sizes 0 through 7 "
        f"in the exactly verified graph P({n},3); none forces all vertices."
    )
    print("This finite check does not establish the claim for all n >= 7.")
    print("VERDICT: CONSISTENT_NO_COUNTEREXAMPLE")


if __name__ == "__main__":
    main()
