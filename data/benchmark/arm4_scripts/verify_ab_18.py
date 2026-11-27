#!/usr/bin/env python3
"""
Exact exhaustive counterexample search for:
    psi_sq(T) <= diss(T) for every finite tree T.

Enumerates every unlabeled tree with 1 <= n <= 8 and every partial
coloring, up to permutation of color names. All mathematical tests use
integers. A time guard permits a clean, honest report on slower machines.
"""

import time

MAX_N = 8
TIME_BUDGET_SECONDS = 12.0
START = time.monotonic()


def expired():
    return time.monotonic() - START >= TIME_BUDGET_SECONDS


def vertices(mask):
    while mask:
        bit = mask & -mask
        yield bit.bit_length() - 1
        mask ^= bit


def is_tree(adj):
    """Verify simplicity, symmetry, connectedness, and the tree edge count."""
    n = len(adj)
    if n == 0:
        return False
    universe = (1 << n) - 1
    for v, neighbors in enumerate(adj):
        if neighbors < 0 or neighbors & ~universe or neighbors & (1 << v):
            return False
        for w in vertices(neighbors):
            if not (adj[w] & (1 << v)):
                return False
    if sum(a.bit_count() for a in adj) != 2 * (n - 1):
        return False

    seen = 1
    pending = [0]
    while pending:
        v = pending.pop()
        for w in vertices(adj[v] & ~seen):
            seen |= 1 << w
            pending.append(w)
    return seen == universe


def canonical_tree_key(adj):
    """
    Complete isomorphism invariant: the minimum rooted parenthesis
    encoding over all possible roots.
    """
    def rooted(v, parent):
        children = [
            rooted(w, v) for w in vertices(adj[v]) if w != parent
        ]
        children.sort()
        return "(" + "".join(children) + ")"

    return min(rooted(v, -1) for v in range(len(adj)))


def next_tree_level(previous):
    """
    Every tree arises by attaching a leaf to a smaller tree.
    Canonical encoding removes exactly the isomorphic duplicates.
    """
    unique = {}
    for adj in previous:
        n = len(adj)
        for v in range(n):
            grown = list(adj)
            grown[v] |= 1 << n
            grown.append(1 << v)
            grown = tuple(grown)
            key = canonical_tree_key(grown)
            unique.setdefault(key, grown)
    return list(unique.values())


def dissociation_number(adj):
    """Exhaust all vertex subsets, returning the exact optimum and a witness."""
    n = len(adj)
    best_size, best_mask = 0, 0
    for subset in range(1 << n):
        size = subset.bit_count()
        if size <= best_size:
            continue
        if all((adj[v] & subset).bit_count() <= 1
               for v in vertices(subset)):
            best_size, best_mask = size, subset
    return best_size, best_mask


def partial_colorings(n):
    """
    Enumerate every partial coloring modulo color-name permutations.

    -1 means uncolored. Nonnegative colors appear in order of first use.
    Each yield contains the coloring, its color-class masks, and the mask
    of all colored vertices.
    """
    assignment = [-1] * n
    classes = []

    def visit(v, colored):
        if v == n:
            yield tuple(assignment), tuple(classes), colored
            return

        assignment[v] = -1
        yield from visit(v + 1, colored)

        bit = 1 << v
        existing = len(classes)
        for color in range(existing):
            assignment[v] = color
            classes[color] |= bit
            yield from visit(v + 1, colored | bit)
            classes[color] ^= bit

        assignment[v] = existing
        classes.append(bit)
        yield from visit(v + 1, colored | bit)
        classes.pop()
        assignment[v] = -1

    yield from visit(0, 0)


def satisfies_sub_quorum(adj, assignment):
    """Independent exact verification directly from the stated definition."""
    if len(assignment) != len(adj):
        return False
    if any(type(c) is not int or c < -1 for c in assignment):
        return False

    for v, color in enumerate(assignment):
        if color == -1:
            continue
        closed = adj[v] | (1 << v)
        colored_count = 0
        same_count = 0
        for w in vertices(closed):
            if assignment[w] != -1:
                colored_count += 1
                same_count += (assignment[w] == color)
        if 2 * same_count < colored_count:
            return False
    return True


def report_counterexample(adj, assignment):
    """
    Recheck every hypothesis and the strict violation independently.
    A valid coloring with k > diss(T) proves psi_sq(T) >= k > diss(T).
    """
    assert is_tree(adj)
    assert satisfies_sub_quorum(adj, assignment)
    used = set(assignment) - {-1}
    diss, subset = dissociation_number(adj)
    assert len(used) > diss

    print("Explicit counterexample, verified using integer arithmetic.")
    print("Vertices:", list(range(len(adj))))
    print("Edges:", [
        (v, w)
        for v in range(len(adj))
        for w in vertices(adj[v])
        if v < w
    ])
    print("Coloring (-1 = uncolored):", list(assignment))
    print("Number of distinct colors:", len(used))
    print("Exact dissociation number:", diss)
    print("Maximum dissociation subset:", list(vertices(subset)))
    print("Verified: finite, simple, undirected, connected, acyclic tree.")
    print("For each colored vertex: (vertex, same-color count, colored count)")
    for v, color in enumerate(assignment):
        if color == -1:
            continue
        neighborhood = list(vertices(adj[v] | (1 << v)))
        same = sum(assignment[w] == color for w in neighborhood)
        total = sum(assignment[w] != -1 for w in neighborhood)
        print((v, same, total), "; exact condition:", 2 * same, ">=", total)
    print("VERDICT: COUNTEREXAMPLE_VERIFIED")


def main():
    # Known counts also check the completeness of the tree generator.
    expected_tree_counts = {
        1: 1, 2: 1, 3: 1, 4: 2, 5: 3, 6: 6, 7: 11, 8: 23
    }
    # Partial colorings of n vertices correspond to partitions of n+1
    # objects, with the extra object designating the uncolored block.
    expected_coloring_counts = {
        1: 2, 2: 5, 3: 15, 4: 52,
        5: 203, 6: 877, 7: 4140, 8: 21147
    }

    trees = [(0,)]
    complete_levels = []
    checked_trees = 0
    checked_colorings = 0
    stopped = False

    for n in range(1, MAX_N + 1):
        if expired():
            stopped = True
            break
        if n > 1:
            trees = next_tree_level(trees)
        assert len(trees) == expected_tree_counts[n]
        assert all(is_tree(adj) for adj in trees)

        colorings = list(partial_colorings(n))
        assert len(colorings) == expected_coloring_counts[n]

        for adj in trees:
            if expired():
                stopped = True
                break

            diss, subset = dissociation_number(adj)

            # Distinct colors on a dissociation set always give a valid
            # sub-quorum coloring, establishing this exact lower bound.
            baseline = [-1] * n
            for color, v in enumerate(vertices(subset)):
                baseline[v] = color
            assert satisfies_sub_quorum(adj, baseline)
            best = diss

            closed = tuple(adj[v] | (1 << v) for v in range(n))
            order = sorted(
                range(n), key=lambda v: closed[v].bit_count(), reverse=True
            )

            for index, (assignment, classes, colored) in enumerate(colorings):
                if index % 512 == 0 and expired():
                    stopped = True
                    break
                checked_colorings += 1
                valid = True
                for v in order:
                    color = assignment[v]
                    if color != -1:
                        same = (closed[v] & classes[color]).bit_count()
                        total = (closed[v] & colored).bit_count()
                        if 2 * same < total:
                            valid = False
                            break
                if valid:
                    best = max(best, len(classes))
                    if len(classes) > diss:
                        report_counterexample(adj, assignment)
                        return

            if stopped:
                break
            assert best == diss
            checked_trees += 1

        if stopped:
            break
        complete_levels.append((n, len(trees), len(colorings)))

    print("All neighborhood inequalities and dissociation tests used exact integers.")
    print("Tree isomorphism classes generated by exhaustive leaf attachment.")
    print("All partial colorings enumerated modulo permutation of color names.")
    for n, tree_count, coloring_count in complete_levels:
        print(
            "n=%d: %d trees; %d partial colorings per tree; "
            "psi_sq(T) = diss(T) in every case."
            % (n, tree_count, coloring_count)
        )
    print("Fully checked trees:", checked_trees)
    print("Partial colorings tested:", checked_colorings)
    if stopped:
        print("Time guard reached; only the completed levels above are exhaustive.")
    print("Finite testing does not establish the proposition for all tree sizes.")
    print("VERDICT: CONSISTENT_NO_COUNTEREXAMPLE")


if __name__ == "__main__":
    main()
