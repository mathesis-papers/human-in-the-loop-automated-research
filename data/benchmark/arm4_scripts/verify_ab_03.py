#!/usr/bin/env python3
"""
Exact counterexample search for the claim that the Cartesian square of every
finite connected well-covered abelian Cayley graph is well-covered.

We test G = Cay(Z/4Z, {1, 3}), the cycle C4, and systematically enumerate
subsets of its 16-vertex Cartesian square. All checks use integer arithmetic.
No external packages are required.
"""

from collections import deque


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def bits(mask):
    """Yield the indices of the set bits of a nonnegative integer."""
    while mask:
        bit = mask & -mask
        yield bit.bit_length() - 1
        mask ^= bit


def independent(mask, adjacency):
    return all((adjacency[v] & mask) == 0 for v in bits(mask))


def maximal_independent(mask, adjacency):
    """Check independence and domination of every vertex outside the set."""
    if not independent(mask, adjacency):
        return False
    full = (1 << len(adjacency)) - 1
    covered = mask
    for v in bits(mask):
        covered |= adjacency[v]
    return covered == full


def connected(adjacency):
    seen = {0}
    queue = deque([0])
    while queue:
        v = queue.popleft()
        for w in bits(adjacency[v]):
            if w not in seen:
                seen.add(w)
                queue.append(w)
    return len(seen) == len(adjacency)


def verify_simple_undirected(adjacency):
    n = len(adjacency)
    full = (1 << n) - 1
    for v in range(n):
        require((adjacency[v] & ~full) == 0, "Invalid vertex in adjacency.")
        require((adjacency[v] & (1 << v)) == 0, "Graph has a loop.")
        for w in range(n):
            require(
                bool(adjacency[v] & (1 << w))
                == bool(adjacency[w] & (1 << v)),
                "Adjacency is not symmetric.",
            )


def certificate(mask, adjacency, labels):
    """Return a checked neighbor certificate for each excluded vertex."""
    require(maximal_independent(mask, adjacency),
            "Set is not maximal independent.")
    result = []
    for v in range(len(adjacency)):
        if not (mask & (1 << v)):
            neighbors_in_set = adjacency[v] & mask
            require(neighbors_in_set != 0,
                    "Excluded vertex has no neighbor in the set.")
            w = (neighbors_in_set & -neighbors_in_set).bit_length() - 1
            result.append((labels[v], labels[w]))
    return result


def main():
    # Explicit finite abelian group: addition modulo four.
    gamma = tuple(range(4))
    add = lambda a, b: (a + b) % 4
    inverse = lambda a: (-a) % 4
    connection_set = frozenset({1, 3})

    # Verify the group axioms directly, including commutativity.
    for a in gamma:
        require(add(0, a) == a and add(a, 0) == a, "Identity failed.")
        require(add(a, inverse(a)) == 0, "Inverse failed.")
        for b in gamma:
            require(add(a, b) in gamma, "Closure failed.")
            require(add(a, b) == add(b, a), "Group is not abelian.")
            for c in gamma:
                require(
                    add(add(a, b), c) == add(a, add(b, c)),
                    "Associativity failed.",
                )

    require(0 not in connection_set, "Connection set contains zero.")
    require(connection_set <= set(gamma), "Invalid connection set.")
    require(
        {inverse(s) for s in connection_set} == set(connection_set),
        "Connection set is not closed under negation.",
    )

    # Construct G from its Cayley definition.
    adjacency_g = [
        sum(1 << w for w in gamma if (w - v) % 4 in connection_set)
        for v in gamma
    ]
    verify_simple_undirected(adjacency_g)
    require(connected(adjacency_g), "G is not connected.")

    # Exhaustively establish well-coveredness of G.
    maximal_sets_g = [
        mask for mask in range(1 << len(gamma))
        if maximal_independent(mask, adjacency_g)
    ]
    sizes_g = {mask.bit_count() for mask in maximal_sets_g}
    require(len(sizes_g) == 1, "G is not well-covered.")

    # Construct the Cartesian square directly from the definition.
    vertices = [(x, y) for x in gamma for y in gamma]
    adjacency_square = []
    for x, y in vertices:
        neighbor_mask = 0
        for j, (u, v) in enumerate(vertices):
            edge = (
                (x == u and bool(adjacency_g[y] & (1 << v)))
                or
                (y == v and bool(adjacency_g[x] & (1 << u)))
            )
            if edge:
                neighbor_mask |= 1 << j
        adjacency_square.append(neighbor_mask)

    verify_simple_undirected(adjacency_square)
    require(connected(adjacency_square), "Cartesian square is not connected.")

    # This parity class provides an explicitly checked reference set.
    reference = sum(
        1 << i
        for i, (x, y) in enumerate(vertices)
        if (x + y) % 2 == 0
    )
    require(maximal_independent(reference, adjacency_square),
            "Reference set is not maximal independent.")

    # Systematic exhaustive search, stopping at the first verified witness.
    # There are only 2^16 = 65,536 candidate subsets.
    tested = 0
    witness = None
    for mask in range(1 << len(vertices)):
        tested += 1
        if mask.bit_count() == reference.bit_count():
            continue
        if maximal_independent(mask, adjacency_square):
            witness = mask
            break

    print("All computations use exact integers.")
    print("Gamma = Z/4Z, with addition modulo 4.")
    print("S = {1, 3}; verified 0 not in S and S = -S.")
    print("Verified finite abelian group axioms, Cayley adjacency,")
    print("simple undirected graph structure, and connectedness.")
    print("G is the cycle C4.")
    print("Exhaustively checked all 16 subsets of G.")
    print("All maximal independent sets of G:",
          [[v for v in bits(mask)] for mask in maximal_sets_g])
    print("Their common cardinality:", next(iter(sizes_g)))
    print("Verified the Cartesian-square adjacency definition exactly.")
    print("Square subsets examined:", tested)

    if witness is not None:
        # Independently recheck both complete witness certificates.
        cert_a = certificate(reference, adjacency_square, vertices)
        cert_b = certificate(witness, adjacency_square, vertices)
        require(reference.bit_count() != witness.bit_count(),
                "Witness cardinalities are equal.")

        print("Maximal independent set A:",
              [vertices[i] for i in bits(reference)])
        print("|A| =", reference.bit_count())
        print("Maximal independent set B:",
              [vertices[i] for i in bits(witness)])
        print("|B| =", witness.bit_count())
        print("Both sets were checked to contain no adjacent pair.")
        print("Maximality certificates below give, for every excluded")
        print("vertex, an adjacent vertex belonging to the indicated set.")
        print("Certificate for A (excluded vertex, neighbor in A):", cert_a)
        print("Certificate for B (excluded vertex, neighbor in B):", cert_b)
        print("Every stated hypothesis holds, but the square has maximal")
        print("independent sets of different cardinalities.")
        print("VERDICT: COUNTEREXAMPLE_VERIFIED")
    else:
        print("Exhaustively checked all 65,536 square subsets; no maximal")
        print("independent set of a different size was found for this G.")
        print("VERDICT: CONSISTENT_NO_COUNTEREXAMPLE")


if __name__ == "__main__":
    main()
