#!/usr/bin/env python3
"""
Search for a counterexample to psi_sq(Q_n) = 2^(n-1).

A coloring is represented by a list:
    -1: uncolored vertex
    nonnegative integer: color label

All mathematical checks use exact integer arithmetic. The search includes:
  * exhaustive enumeration of all partial colorings, up to color relabeling,
    of Q_2 and Q_3;
  * exhaustive testing of all uniquely colored vertex subsets of Q_4;
  * randomized searches on Q_4 through Q_8, repairing violated constraints
    by merging colors or removing colored vertices.

Failure to find a witness is only consistency on the tested instances.
"""

import random
import sys
import time

START = time.monotonic()
DEADLINE = START + 11.0
RNG = random.Random(120012)
GRAPHS = {}
STATS = {
    "exhaustive_partial_colorings": 0,
    "unique_color_subsets_Q4": 0,
    "random_initial_states": 0,
    "random_states_checked": 0,
    "valid_random_states": 0,
}
BEST = {}


def cube(n):
    if n not in GRAPHS:
        size = 1 << n
        neighbors = [
            tuple(v ^ (1 << coordinate) for coordinate in range(n))
            for v in range(size)
        ]
        GRAPHS[n] = neighbors
    return GRAPHS[n]


def verify(n, coloring):
    """Independently verify every hypothesis and the proposed strict violation."""
    if type(n) is not int or n < 2:
        return False, None
    size = 1 << n
    if len(coloring) != size:
        return False, None
    if any(type(c) is not int or c < -1 for c in coloring):
        return False, None

    # Construct and check the actual n-dimensional hypercube.
    adjacency = [
        {v ^ (1 << coordinate) for coordinate in range(n)}
        for v in range(size)
    ]
    for v, neighbors in enumerate(adjacency):
        if len(neighbors) != n or v in neighbors:
            return False, None
        for u in neighbors:
            if not 0 <= u < size:
                return False, None
            if (u ^ v).bit_count() != 1 or v not in adjacency[u]:
                return False, None

    reached = {0}
    stack = [0]
    while stack:
        v = stack.pop()
        for u in adjacency[v]:
            if u not in reached:
                reached.add(u)
                stack.append(u)
    if len(reached) != size:
        return False, None

    details = []
    colors = set()
    for v, color in enumerate(coloring):
        if color == -1:
            continue
        colors.add(color)
        closed = adjacency[v] | {v}
        colored_count = sum(coloring[u] != -1 for u in closed)
        same_count = sum(coloring[u] == color for u in closed)
        # Exactly the stated rule, including v itself.
        if 2 * same_count < colored_count:
            return False, None
        details.append((v, same_count, colored_count))

    if len(colors) <= (1 << (n - 1)):
        return False, None
    return True, details


def report_witness(n, coloring):
    valid, details = verify(n, coloring)
    if not valid:
        return False
    colors = sorted({c for c in coloring if c != -1})
    print("Explicit counterexample, independently verified using integers.")
    print("n =", n)
    print("Vertices are integers 0 through", (1 << n) - 1)
    print("Edges join vertices whose binary strings differ in one coordinate.")
    print("Number of colors =", len(colors))
    print("Claimed maximum =", 1 << (n - 1))
    print("Color classes:")
    for color in colors:
        vertices = [v for v, c in enumerate(coloring) if c == color]
        print(" ", color, ":", [format(v, "0%db" % n) for v in vertices])
    print("Uncolored vertices:",
          [format(v, "0%db" % n)
           for v, c in enumerate(coloring) if c == -1])
    print("Closed-neighborhood checks: vertex, same-color count, colored count")
    for v, same, total in details:
        print(" ", format(v, "0%db" % n), same, total,
              "; exact check:", 2 * same, ">=", total)
    print("VERDICT: COUNTEREXAMPLE_VERIFIED")
    sys.exit(0)


def evaluate(n, coloring):
    """Return the color count and vertices violating the exact coloring rule."""
    neighbors = cube(n)
    colors = set()
    bad = []
    for v, color in enumerate(coloring):
        if color == -1:
            continue
        colors.add(color)
        total = 1
        same = 1
        for u in neighbors[v]:
            other = coloring[u]
            if other != -1:
                total += 1
                if other == color:
                    same += 1
        if 2 * same < total:
            bad.append(v)
    return len(colors), bad


def record_valid(n, coloring, count):
    BEST[n] = max(BEST.get(n, 0), count)
    if count > (1 << (n - 1)):
        report_witness(n, coloring)


def exhaustive_partial_colorings(n):
    """
    Restricted-growth enumeration: every partial coloring appears exactly once
    modulo permutation of its nonnegative color labels.
    """
    size = 1 << n
    coloring = [-1] * size

    def visit(position, used):
        if position == size:
            STATS["exhaustive_partial_colorings"] += 1
            count, bad = evaluate(n, coloring)
            if not bad:
                record_valid(n, coloring, count)
            return

        coloring[position] = -1
        visit(position + 1, used)
        for color in range(used):
            coloring[position] = color
            visit(position + 1, used)
        coloring[position] = used
        visit(position + 1, used + 1)
        coloring[position] = -1

    visit(0, 0)


def exhaustive_unique_subsets_q4():
    """
    With a different color at every selected vertex, the rule is equivalent
    to the selected induced subgraph having maximum degree at most one.
    Test all 2^16 subsets exactly.
    """
    n = 4
    size = 1 << n
    neighbor_masks = [
        sum(1 << u for u in neighbors) for neighbors in cube(n)
    ]
    for mask in range(1 << size):
        STATS["unique_color_subsets_Q4"] += 1
        remaining = mask
        valid = True
        while remaining:
            bit = remaining & -remaining
            v = bit.bit_length() - 1
            if (mask & neighbor_masks[v]).bit_count() > 1:
                valid = False
                break
            remaining ^= bit
        if valid:
            count = mask.bit_count()
            coloring = [v if mask & (1 << v) else -1 for v in range(size)]
            record_valid(n, coloring, count)


def randomized_search():
    dimensions = (4, 5, 6, 7, 8)
    attempt = 0
    while time.monotonic() < DEADLINE:
        n = dimensions[attempt % len(dimensions)]
        attempt += 1
        size = 1 << n
        neighbors = cube(n)

        # Mostly start with distinct colors; some starts contain shared colors
        # to explore configurations not reached by a single repair trajectory.
        density = RNG.uniform(0.35, 1.0)
        shared = RNG.random() < 0.3
        palette_size = RNG.randint(2, max(2, size // 2))
        coloring = [
            (RNG.randrange(palette_size) if shared else v)
            if RNG.random() < density else -1
            for v in range(size)
        ]
        STATS["random_initial_states"] += 1

        # Each repair either merges two whole classes or removes a vertex.
        # Thus the trajectory is finite even without the time bound.
        for _ in range(2 * size + 1):
            if time.monotonic() >= DEADLINE:
                return
            count, bad = evaluate(n, coloring)
            STATS["random_states_checked"] += 1
            if not bad:
                STATS["valid_random_states"] += 1
                record_valid(n, coloring, count)
                break

            # Merging and deletion cannot increase the color count.
            if count <= (1 << (n - 1)):
                break

            v = RNG.choice(bad)
            own = coloring[v]
            alternatives = [
                u for u in neighbors[v]
                if coloring[u] != -1 and coloring[u] != own
            ]
            if not alternatives:
                raise AssertionError("A violated vertex must have another-colored neighbor.")

            if RNG.random() < 0.70:
                other = coloring[RNG.choice(alternatives)]
                coloring = [own if c == other else c for c in coloring]
            else:
                # Either remove the violated vertex or remove one of the
                # other-colored neighbors that causes its violation.
                target = v if RNG.random() < 0.5 else RNG.choice(alternatives)
                coloring[target] = -1


def main():
    # Verify the claimed lower-bound construction for every searched dimension.
    for n in range(2, 9):
        coloring = [
            v if v.bit_count() % 2 == 0 else -1
            for v in range(1 << n)
        ]
        count, bad = evaluate(n, coloring)
        assert not bad and count == (1 << (n - 1))
        record_valid(n, coloring, count)

    exhaustive_partial_colorings(2)
    exhaustive_partial_colorings(3)
    exhaustive_unique_subsets_q4()
    randomized_search()

    print("All coloring inequalities were tested with exact integer arithmetic.")
    print("Exhaustively enumerated every partial coloring up to color relabeling "
          "of Q_2 and Q_3:",
          STATS["exhaustive_partial_colorings"], "instances.")
    print("Exhaustively tested uniquely colored subsets of Q_4:",
          STATS["unique_color_subsets_Q4"], "instances.")
    print("Randomized repair search on Q_4 through Q_8:",
          STATS["random_initial_states"], "initial states;",
          STATS["random_states_checked"], "states checked;",
          STATS["valid_random_states"], "valid states encountered.")
    print("Largest verified valid color counts:",
          ", ".join("Q_%d: %d" % (n, BEST[n]) for n in sorted(BEST)))
    print("The searches for n >= 4 do not exhaust all partial colorings.")
    print("Elapsed seconds: %.3f" % (time.monotonic() - START))
    print("VERDICT: CONSISTENT_NO_COUNTEREXAMPLE")


if __name__ == "__main__":
    main()
