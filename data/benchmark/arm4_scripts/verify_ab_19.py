#!/usr/bin/env python3
"""
Exact exhaustive verification of the claim for m = 2, ..., 7.

Every independent set is enumerated exactly once by processing rows in order
and either leaving the row empty or placing a rook in an unused column.
Maximality is checked using the actual Cartesian-product graph.

All calculations use integers, sets, and bit masks; no floating-point
tolerances or external libraries are needed.
"""

from math import comb, factorial


def make_graph(m):
    """Construct K_m box K_m directly from the Cartesian-product definition."""
    assert isinstance(m, int) and m >= 2
    vertices = [(i, j) for i in range(m) for j in range(m)]
    adjacency = [0] * (m * m)

    for u, (i, j) in enumerate(vertices):
        for v, (r, c) in enumerate(vertices):
            if u != v and ((i == r and j != c) or (j == c and i != r)):
                adjacency[u] |= 1 << v

    # Verify the concrete graph exactly, including simplicity and symmetry.
    for u, (i, j) in enumerate(vertices):
        assert not (adjacency[u] & (1 << u))
        assert adjacency[u].bit_count() == 2 * (m - 1)
        for v, (r, c) in enumerate(vertices):
            expected = u != v and (i == r or j == c)
            assert bool(adjacency[u] & (1 << v)) == expected
            assert bool(adjacency[u] & (1 << v)) == bool(
                adjacency[v] & (1 << u)
            )

    # Connectivity is also checked, although it is not an extra hypothesis.
    reached = 1
    frontier = 1
    while frontier:
        neighbors = 0
        remaining = frontier
        while remaining:
            bit = remaining & -remaining
            remaining -= bit
            neighbors |= adjacency[bit.bit_length() - 1]
        frontier = neighbors & ~reached
        reached |= frontier
    assert reached == (1 << (m * m)) - 1
    return vertices, adjacency


def independently_verify_witness(m, cells):
    """Recheck every hypothesis and the violation without enumeration masks."""
    if type(m) is not int or m < 2:
        return False
    if len(cells) != len(set(cells)):
        return False
    if any(
        type(i) is not int
        or type(j) is not int
        or not (0 <= i < m and 0 <= j < m)
        for i, j in cells
    ):
        return False

    # The ambient graph is exactly the stated Cartesian square.
    vertices, adjacency = make_graph(m)
    chosen = set(cells)

    # Independence: distinct chosen cells share neither row nor column.
    for a in range(len(cells)):
        for b in range(a + 1, len(cells)):
            if cells[a][0] == cells[b][0] or cells[a][1] == cells[b][1]:
                return False

    # Inclusion maximality: each outside vertex has a chosen neighbor.
    for u, cell in enumerate(vertices):
        if cell not in chosen:
            if not any(
                adjacency[u] & (1 << (i * m + j)) for i, j in cells
            ):
                return False

    return len(cells) != m


def examine(m):
    vertices, adjacency = make_graph(m)
    full = (1 << (m * m)) - 1
    closed = [adjacency[u] | (1 << u) for u in range(m * m)]
    counts = [0] * (m + 1)
    maximal_counts = [0] * (m + 1)
    witness = None
    cells = []

    def visit(row, used_columns, selected, dominated):
        nonlocal witness
        if witness is not None:
            return

        if row == m:
            size = len(cells)
            counts[size] += 1

            # Direct exact independence check in the constructed graph.
            remaining = selected
            while remaining:
                bit = remaining & -remaining
                remaining -= bit
                u = bit.bit_length() - 1
                assert (adjacency[u] & selected) == 0

            # For an independent set, maximality is equivalent to domination.
            maximal = dominated == full
            if maximal:
                maximal_counts[size] += 1
                if size != m:
                    candidate = list(cells)
                    if not independently_verify_witness(m, candidate):
                        raise RuntimeError("Candidate failed independent verification")
                    witness = candidate
            return

        # No rook in this row.
        visit(row + 1, used_columns, selected, dominated)

        # One rook in this row, in each currently unused column.
        available = ((1 << m) - 1) & ~used_columns
        while available:
            column_bit = available & -available
            available -= column_bit
            col = column_bit.bit_length() - 1
            u = row * m + col
            assert not (adjacency[u] & selected)
            cells.append((row, col))
            visit(
                row + 1,
                used_columns | column_bit,
                selected | (1 << u),
                dominated | closed[u],
            )
            cells.pop()

    visit(0, 0, 0, 0)

    if witness is None:
        # Exact enumeration totals provide an additional completeness check:
        # choose occupied rows, choose occupied columns, then biject them.
        expected = [
            comb(m, k) * comb(m, k) * factorial(k) for k in range(m + 1)
        ]
        assert counts == expected

    return counts, maximal_counts, witness


def main():
    total = 0
    summaries = []
    for m in range(2, 8):
        counts, maximal_counts, witness = examine(m)
        if witness is not None:
            print("Exact counterexample in K_m box K_m")
            print("m =", m)
            print("Vertices use zero-based row and column indices.")
            print("Independent set =", witness)
            print("Cardinality =", len(witness), "; required cardinality =", m)
            print(
                "Verified exactly: integer m >= 2, Cartesian-square adjacency, "
                "valid distinct vertices, independence, and inclusion maximality."
            )
            print("VERDICT: COUNTEREXAMPLE_VERIFIED")
            return

        total += sum(counts)
        sizes = [k for k, count in enumerate(maximal_counts) if count]
        summaries.append(
            f"m={m}: {sum(counts)} independent sets exhaustively checked; "
            f"{sum(maximal_counts)} maximal; maximal cardinalities={sizes}"
        )

    for summary in summaries:
        print(summary)
    print(
        f"All {total} independent sets for m=2 through 7 were checked exactly. "
        "Every maximal independent set tested has cardinality m. "
        "This finite exhaustive check does not establish the universal claim."
    )
    print("VERDICT: CONSISTENT_NO_COUNTEREXAMPLE")


if __name__ == "__main__":
    main()
