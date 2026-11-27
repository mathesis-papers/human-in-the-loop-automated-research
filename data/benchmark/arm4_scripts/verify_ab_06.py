#!/usr/bin/env python3
"""
Search for counterexamples to quantum-subentropy subadditivity among diagonal
bipartite density matrices.

Every tested state is specified by a nonnegative integer table W:
    rho_AB = diag(W.flatten()) / sum(W).
Thus positivity, Hermiticity, normalization, and both partial traces are
verified using exact integer/Fraction arithmetic.

Subentropy is evaluated using high-precision Decimal arithmetic and confluent
divided differences, including repeated eigenvalues and zero eigenvalues.
A claimed violation must exceed 1e-6 and survive independent evaluations at
80 and 120 decimal digits. The search has a conservative internal time limit.

Diagonal states form a restricted family: absence of a witness in this search
does not prove the proposition for arbitrary quantum states.
"""

from decimal import Decimal, localcontext
from fractions import Fraction
from itertools import product
from math import comb
import random
import time


START = time.monotonic()
SEARCH_SECONDS = 11.0
VIOLATION_THRESHOLD = Decimal("0.000001")
CONFIRMATION_AGREEMENT = Decimal("1e-45")

tested = 0
families = {}
largest_gap = None
largest_gap_table = None


def before_deadline():
    return time.monotonic() - START < SEARCH_SECONDS


def exact_spectra(weights):
    """Verify all density-matrix hypotheses and return exact spectra."""
    assert isinstance(weights, (tuple, list)) and len(weights) >= 2
    rows = len(weights)
    cols = len(weights[0])
    assert cols >= 2
    assert all(len(row) == cols for row in weights)
    assert all(type(w) is int and w >= 0 for row in weights for w in row)

    total = sum(sum(row) for row in weights)
    assert total > 0

    joint = tuple(Fraction(w, total) for row in weights for w in row)
    marginal_a = tuple(
        Fraction(sum(row), total) for row in weights
    )
    marginal_b = tuple(
        Fraction(sum(weights[i][j] for i in range(rows)), total)
        for j in range(cols)
    )

    # These spectra specify real diagonal matrices, so Hermiticity is exact.
    # A diagonal matrix is PSD exactly when all its diagonal entries are >= 0.
    for spectrum in (joint, marginal_a, marginal_b):
        assert all(isinstance(x, Fraction) and x >= 0 for x in spectrum)
        assert sum(spectrum, Fraction(0)) == 1

    # Verify the partial traces entry by entry, with exact arithmetic.
    for i in range(rows):
        assert sum(joint[i * cols + j] for j in range(cols)) == marginal_a[i]
    for j in range(cols):
        assert sum(joint[i * cols + j] for i in range(rows)) == marginal_b[j]

    return joint, marginal_a, marginal_b


def subentropy(spectrum, precision):
    """
    Q = -[x_1,...,x_n](x^n log x), evaluated by confluent divided differences.

    Zero eigenvalues may be removed: for positive distinct eigenvalues their
    factors cancel from the defining formula, and continuity gives the same
    result with multiplicities. Rank-one states have Q = 0.
    """
    positive = tuple(sorted(x for x in spectrum if x > 0))
    n = len(positive)
    assert n >= 1

    if n == 1:
        assert positive[0] == 1
        return Decimal(0)

    with localcontext() as ctx:
        ctx.prec = precision
        nodes = [
            Decimal(x.numerator) / Decimal(x.denominator)
            for x in positive
        ]
        logs = [x.ln() for x in nodes]
        harmonic = [Decimal(0)]
        for k in range(1, n + 1):
            harmonic.append(harmonic[-1] + Decimal(1) / Decimal(k))

        values = [nodes[i] ** n * logs[i] for i in range(n)]

        for order in range(1, n):
            next_values = []
            for i in range(n - order):
                if positive[i] == positive[i + order]:
                    # f^(order)(x)/order!, for f(x) = x^n log(x).
                    value = (
                        Decimal(comb(n, order))
                        * nodes[i] ** (n - order)
                        * (
                            logs[i]
                            + harmonic[n]
                            - harmonic[n - order]
                        )
                    )
                else:
                    value = (
                        (values[i + 1] - values[i])
                        / (nodes[i + order] - nodes[i])
                    )
                next_values.append(value)
            values = next_values

        return +(-values[0])


def evaluate(spectra, precision):
    with localcontext() as ctx:
        ctx.prec = precision
        q_joint, q_a, q_b = (
            subentropy(spectrum, precision) for spectrum in spectra
        )
        return q_joint, q_a, q_b, q_joint - q_a - q_b


def check(weights, family):
    global tested, largest_gap, largest_gap_table

    spectra = exact_spectra(weights)
    result = evaluate(spectra, 80)
    gap = result[3]

    tested += 1
    families[family] = families.get(family, 0) + 1
    if largest_gap is None or gap > largest_gap:
        largest_gap = gap
        largest_gap_table = tuple(tuple(row) for row in weights)

    if gap <= VIOLATION_THRESHOLD:
        return False

    # Recheck every hypothesis and recompute with substantially more precision.
    spectra_again = exact_spectra(weights)
    assert spectra_again == spectra
    confirmed = evaluate(spectra_again, 120)

    with localcontext() as ctx:
        ctx.prec = 120
        agreement = max(abs(x - y) for x, y in zip(result, confirmed))

    if (
        confirmed[3] <= VIOLATION_THRESHOLD
        or agreement >= CONFIRMATION_AGREEMENT
    ):
        return False

    rows, cols = len(weights), len(weights[0])
    total = sum(map(sum, weights))
    print("Explicit diagonal bipartite density-matrix witness")
    print("Subsystem dimensions:", rows, "x", cols)
    print("Integer weight table:", [list(row) for row in weights])
    print("Normalization denominator:", total)
    print("rho_AB diagonal:", [str(x) for x in spectra[0]])
    print("rho_A diagonal:", [str(x) for x in spectra[1]])
    print("rho_B diagonal:", [str(x) for x in spectra[2]])
    print("All entries are exact nonnegative fractions summing to one.")
    print("Hermiticity, positive semidefiniteness, and partial traces verified.")
    print("Repeated and zero eigenvalues use the continuous extension.")
    print("Q(rho_AB) =", confirmed[0])
    print("Q(rho_A)  =", confirmed[1])
    print("Q(rho_B)  =", confirmed[2])
    print("Q(rho_AB) - Q(rho_A) - Q(rho_B) =", confirmed[3])
    print("80/120-digit agreement error =", agreement)
    print("VERDICT: COUNTEREXAMPLE_VERIFIED")
    return True


def self_check():
    # Q(I_n/n) = log(n) - H_n + 1.
    for n in (2, 3, 4, 6):
        spectrum = (Fraction(1, n),) * n
        actual = subentropy(spectrum, 80)
        with localcontext() as ctx:
            ctx.prec = 80
            expected = (
                Decimal(n).ln()
                - sum((Decimal(1) / Decimal(k) for k in range(1, n + 1)),
                      Decimal(0))
                + Decimal(1)
            )
            assert abs(actual - expected) < Decimal("1e-65")

    assert subentropy((Fraction(1), Fraction(0)), 80) == 0
    base = (Fraction(1, 4), Fraction(3, 4))
    assert subentropy(base, 80) == subentropy(base + (Fraction(0),), 80)


def run():
    self_check()

    # Product states, including spectra approaching a pure state.
    # Product eigenvalues often repeat, exercising the continuous extension.
    pairs = [
        (1, 1), (1, 2), (1, 3), (1, 9), (1, 99),
        (1, 999), (1, 9999), (1, 999999),
    ]
    for a, b in product(pairs, repeat=2):
        table = tuple(tuple(x * y for y in b) for x in a)
        if check(table, "exact product states"):
            return

    # Pure marginals: verify the asserted equality on concrete instances.
    for row in ((1, 1), (1, 9), (1, 2, 3), (1, 1, 1, 1)):
        table = (row, (0,) * len(row))
        if check(table, "pure-marginal boundary"):
            return

    # Exhaustive enumeration at each completed total:
    # all nonnegative 2x2 integer tables with that total.
    completed_totals = []
    for total in range(1, 19):
        complete = True
        for a in range(total + 1):
            if not complete:
                break
            for b in range(total - a + 1):
                if not complete:
                    break
                for c in range(total - a - b + 1):
                    if not before_deadline():
                        complete = False
                        break
                    d = total - a - b - c
                    if check(((a, b), (c, d)), "systematic 2x2 tables"):
                        return
        if complete:
            completed_totals.append(total)
        else:
            break

    # Deterministic seeded sampling in larger classical state spaces.
    rng = random.Random(608062026)
    dimensions = ((2, 2), (2, 3), (3, 3))
    for iteration in range(2500):
        if not before_deadline():
            break
        rows, cols = dimensions[iteration % len(dimensions)]
        mode = iteration % 4
        if mode == 0:
            flat = [rng.randrange(0, 21) for _ in range(rows * cols)]
        elif mode == 1:
            flat = [rng.choice((0, 0, 1, 2, 10, 100, 10000))
                    for _ in range(rows * cols)]
        elif mode == 2:
            left = [rng.randrange(1, 101) for _ in range(rows)]
            right = [rng.randrange(1, 101) for _ in range(cols)]
            flat = [x * y for x in left for y in right]
        else:
            flat = [rng.randrange(0, 4) for _ in range(rows * cols)]
            flat[rng.randrange(rows * cols)] += 10 ** rng.randrange(2, 7)

        if not any(flat):
            flat[0] = 1
        table = tuple(
            tuple(flat[i * cols:(i + 1) * cols]) for i in range(rows)
        )
        if check(table, "seeded diagonal-state search"):
            return

    print("Subentropy evaluator passed pure-state and maximally-mixed checks.")
    print("Density matrices checked:", tested)
    print("Checks by family:", families)
    print("Fully enumerated 2x2 integer-table totals:", completed_totals)
    print("Every tested state and both partial traces verified exactly.")
    print("Subentropy evaluated at 80 decimal digits with multiplicities.")
    print("Required violation margin:", VIOLATION_THRESHOLD)
    print("Largest observed Q(AB)-Q(A)-Q(B):", largest_gap)
    print("Scope: diagonal bipartite states; this search is not a general proof.")
    print("VERDICT: CONSISTENT_NO_COUNTEREXAMPLE")


if __name__ == "__main__":
    run()
