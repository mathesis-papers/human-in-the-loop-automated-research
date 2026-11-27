#!/usr/bin/env python3
"""
Exact counterexample search for blinded claim ab_14.

Graphs tested are finite, nonempty, undirected, simple, and cubic. This is
a subclass of the stated hypotheses, so a counterexample here suffices.

For each completed graph search, enumerate EVERY partial vertex coloring,
up to permutation of color names. Each vertex is either uncolored or belongs
to a color block. Restricted-growth enumeration lists every such partition
exactly once. Check the sub-quorum condition using integer arithmetic.

An upper-bound counterexample needs one verified coloring.
A lower-bound counterexample requires completed exhaustive enumeration proving
that the exact maximum number of colors is less than n/2.

The time limit bounds the search, not its mathematical conclusions: incomplete
enumerations are never used to certify a lower-bound counterexample.
"""
import random
import time

START = time.monotonic()
DEADLINE = START + 12.0


class SearchTimeout(Exception):
    pass


class UpperWitness(Exception):
    def __init__(self, blocks):
        self.blocks = tuple(blocks)


def check_time():
    if time.monotonic() >= DEADLINE:
        raise SearchTimeout


def make_graph(n, edges):
    adjacency = [0] * n
    for u, v in edges:
        if not (0 <= u < n and 0 <= v < n) or u == v:
            raise ValueError("Invalid edge or loop")
        if (adjacency[u] >> v) & 1:
            raise ValueError("Repeated edge")
        adjacency[u] |= 1 << v
        adjacency[v] |= 1 << u
    return tuple(adjacency)


def verify_graph(adjacency):
    n = len(adjacency)
    assert n > 0 and n % 2 == 0
    universe = (1 << n) - 1
    for v, neighbors in enumerate(adjacency):
        assert isinstance(neighbors, int)
        assert neighbors >= 0 and neighbors & ~universe == 0
        assert not ((neighbors >> v) & 1)
        assert neighbors.bit_count() == 3
        for u in range(n):
            assert ((neighbors >> u) & 1) == ((adjacency[u] >> v) & 1)
    assert sum(a.bit_count() for a in adjacency) == 3 * n


def verify_coloring(adjacency, blocks):
    """Verify all hypotheses for the coloring with exact integer comparisons."""
    n = len(adjacency)
    universe = (1 << n) - 1
    selected = 0
    for block in blocks:
        assert isinstance(block, int) and block > 0
        assert block & ~universe == 0
        assert selected & block == 0
        selected |= block

    for block in blocks:
        remaining = block
        while remaining:
            bit = remaining & -remaining
            remaining -= bit
            v = bit.bit_length() - 1
            colored_closed = 1 + (adjacency[v] & selected).bit_count()
            same_closed = 1 + (adjacency[v] & block).bit_count()
            if 2 * same_closed < colored_closed:
                return False
    return True


def exact_search(adjacency):
    """
    Return (best_color_count, best_blocks, completed, leaves_examined).

    A separate uncolored choice plus restricted-growth color labels enumerates
    all partial colorings modulo color-name permutations.
    """
    verify_graph(adjacency)
    n = len(adjacency)
    blocks = []
    best = 0
    best_blocks = ()
    leaves = 0
    nodes = 0

    def visit(v, selected):
        nonlocal best, best_blocks, leaves, nodes
        nodes += 1
        if (nodes & 1023) == 0:
            check_time()

        if v == n:
            leaves += 1
            for block in blocks:
                remaining = block
                while remaining:
                    bit = remaining & -remaining
                    remaining -= bit
                    u = bit.bit_length() - 1
                    # The vertex itself contributes one to both counts.
                    if 2 * (1 + (adjacency[u] & block).bit_count()) < (
                        1 + (adjacency[u] & selected).bit_count()
                    ):
                        return

            count = len(blocks)
            if count > best:
                best = count
                best_blocks = tuple(blocks)
            if 5 * count > 3 * n:
                raise UpperWitness(blocks)
            return

        bit = 1 << v

        # Give v a fresh color.
        blocks.append(bit)
        visit(v + 1, selected | bit)
        blocks.pop()

        # Give v any previously introduced color.
        for j in range(len(blocks)):
            blocks[j] |= bit
            visit(v + 1, selected | bit)
            blocks[j] ^= bit

        # Leave v uncolored.
        visit(v + 1, selected)

    try:
        check_time()
        visit(0, 0)
        return best, best_blocks, True, leaves
    except SearchTimeout:
        return best, best_blocks, False, leaves


def all_labeled_cubic_graphs(n):
    """Exhaustively generate simple cubic graphs on labeled vertices 0,...,n-1."""
    adjacency = [0] * n
    degree = [0] * n
    calls = 0

    def recurse(v):
        nonlocal calls
        calls += 1
        if (calls & 255) == 0:
            check_time()

        while v < n and degree[v] == 3:
            v += 1
        if v == n:
            yield tuple(adjacency)
            return

        needed = 3 - degree[v]
        available = [
            u for u in range(v + 1, n)
            if degree[u] < 3 and not ((adjacency[v] >> u) & 1)
        ]

        def choose(start, remaining):
            if remaining == 0:
                yield from recurse(v + 1)
                return
            for j in range(start, len(available) - remaining + 1):
                u = available[j]
                adjacency[v] |= 1 << u
                adjacency[u] |= 1 << v
                degree[v] += 1
                degree[u] += 1
                yield from choose(j + 1, remaining - 1)
                degree[v] -= 1
                degree[u] -= 1
                adjacency[v] ^= 1 << u
                adjacency[u] ^= 1 << v

        yield from choose(0, needed)

    yield from recurse(0)


def prism(m):
    edges = []
    for i in range(m):
        edges.append((i, (i + 1) % m))
        edges.append((m + i, m + (i + 1) % m))
        edges.append((i, m + i))
    return make_graph(2 * m, edges)


def petersen():
    edges = []
    for i in range(5):
        edges.append((i, (i + 1) % 5))
        edges.append((i, 5 + i))
        edges.append((5 + i, 5 + (i + 2) % 5))
    return make_graph(10, edges)


def random_cubic(n, rng):
    # Rejection sampling from the configuration model.
    for attempt in range(2000):
        if (attempt & 31) == 0:
            check_time()
        stubs = [v for v in range(n) for _ in range(3)]
        rng.shuffle(stubs)
        edges = set()
        valid = True
        for j in range(0, len(stubs), 2):
            u, v = sorted((stubs[j], stubs[j + 1]))
            if u == v or (u, v) in edges:
                valid = False
                break
            edges.add((u, v))
        if valid:
            return make_graph(n, sorted(edges))
    return None


def graph_candidates():
    # All labeled simple cubic graphs at these orders, connected or otherwise.
    for n in (4, 6):
        for index, adjacency in enumerate(all_labeled_cubic_graphs(n), 1):
            yield f"exhaustive labeled order {n}, graph {index}", adjacency

    yield "cube (4-prism)", prism(4)
    yield "Petersen graph", petersen()
    yield "5-prism", prism(5)

    rng = random.Random(140014)
    for n, count in ((8, 24), (10, 12), (12, 4)):
        for index in range(count):
            adjacency = random_cubic(n, rng)
            if adjacency is not None:
                yield f"seeded cubic sample n={n}, index={index}", adjacency


def print_graph(adjacency):
    print("Vertices:", list(range(len(adjacency))))
    print("Edges:", [
        (u, v)
        for u in range(len(adjacency))
        for v in range(u + 1, len(adjacency))
        if (adjacency[u] >> v) & 1
    ])


def print_coloring(adjacency, blocks):
    selected = 0
    for block in blocks:
        selected |= block
    print("Color classes:", [
        [v for v in range(len(adjacency)) if (block >> v) & 1]
        for block in blocks
    ])
    print("Uncolored vertices:", [
        v for v in range(len(adjacency)) if not ((selected >> v) & 1)
    ])
    print("Exact quorum checks (vertex, same-color closed, colored closed):")
    for block in blocks:
        for v in range(len(adjacency)):
            if (block >> v) & 1:
                same = 1 + (adjacency[v] & block).bit_count()
                total = 1 + (adjacency[v] & selected).bit_count()
                assert 2 * same >= total
                print((v, same, total))


def main():
    completed = 0
    total_leaves = 0
    seen = set()
    maxima = {}
    interrupted = False

    try:
        for description, adjacency in graph_candidates():
            check_time()
            if adjacency in seen:
                continue
            seen.add(adjacency)
            verify_graph(adjacency)
            n = len(adjacency)

            try:
                best, blocks, finished, leaves = exact_search(adjacency)
            except UpperWitness as witness:
                verify_graph(adjacency)
                assert verify_coloring(adjacency, witness.blocks)
                k = len(witness.blocks)
                assert 5 * k > 3 * n
                print("Verified upper-bound counterexample:", description)
                print_graph(adjacency)
                print_coloring(adjacency, witness.blocks)
                print(f"psi_sq(G) >= {k}; 5*{k} = {5*k} > 3*{n} = {3*n}.")
                print("VERDICT: COUNTEREXAMPLE_VERIFIED")
                return

            total_leaves += leaves
            assert verify_coloring(adjacency, blocks)

            if not finished:
                interrupted = True
                break

            completed += 1
            maxima.setdefault(n, set()).add(best)

            if 2 * best < n:
                # Only a completed exhaustive enumeration can reach this branch.
                verify_graph(adjacency)
                assert verify_coloring(adjacency, blocks)
                assert finished and 2 * best < n
                print("Verified lower-bound counterexample:", description)
                print_graph(adjacency)
                print("Every partial coloring was enumerated, modulo color names.")
                print("Colorings examined for this graph:", leaves)
                print("Exact maximum psi_sq(G):", best)
                print_coloring(adjacency, blocks)
                print(f"2*psi_sq(G) = {2*best} < n = {n}.")
                print("VERDICT: COUNTEREXAMPLE_VERIFIED")
                return

    except SearchTimeout:
        interrupted = True

    print("Exact arithmetic throughout; graph and coloring hypotheses checked.")
    print("Completed exhaustive partial-coloring searches:", completed)
    print("Fully examined coloring assignments:", total_leaves)
    print("Exact maxima observed, grouped by vertex count:",
          {n: sorted(values) for n, values in sorted(maxima.items())})
    print("Time-bounded search stopped early:", interrupted)
    print("No incomplete search was used to certify a lower-bound violation.")
    print("This finite search does not prove the general proposition.")
    print("VERDICT: CONSISTENT_NO_COUNTEREXAMPLE")


if __name__ == "__main__":
    main()
