#!/usr/bin/env python3
"""Exact, systematic verification of blinded claim ab_04.

All calculations use rational arithmetic. No numerical square-root routines
or floating-point tolerances are needed.

Construct R = S^2, P = R, and Q = S^(-1) T^2 S^(-1), with S positive
definite and T positive semidefinite. Then the proposed square roots can
be verified exactly:
    sqrt(R) = S,
    sqrt(S P S) = R,
    sqrt(S Q S) = T.

The script independently checks every hypothesis and each square-root
certificate before comparing the two fidelities. The construction permits
noncommuting matrices and singular or zero Q.
"""

from fractions import Fraction as F
from itertools import combinations, permutations, product
import random


def matrix(rows):
    return tuple(tuple(F(x) for x in row) for row in rows)


def identity(n):
    return matrix([[int(i == j) for j in range(n)] for i in range(n)])


def transpose(a):
    return tuple(zip(*a))


def multiply(a, b):
    bt = transpose(b)
    return tuple(
        tuple(sum((x * y for x, y in zip(row, col)), F(0)) for col in bt)
        for row in a
    )


def determinant(a):
    n = len(a)
    result = F(0)
    for perm in permutations(range(n)):
        inversions = sum(
            perm[i] > perm[j] for i in range(n) for j in range(i + 1, n)
        )
        term = F(-1 if inversions % 2 else 1)
        for i in range(n):
            term *= a[i][perm[i]]
        result += term
    return result


def principal_submatrix(a, indices):
    return tuple(tuple(a[i][j] for j in indices) for i in indices)


def hermitian(a):
    # All entries are rational and real, so Hermitian means symmetric.
    return (
        len(a) > 0
        and all(len(row) == len(a) for row in a)
        and a == transpose(a)
    )


def positive_definite(a):
    # Sylvester's criterion, applied exactly to a real symmetric matrix.
    return hermitian(a) and all(
        determinant(principal_submatrix(a, tuple(range(k)))) > 0
        for k in range(1, len(a) + 1)
    )


def positive_semidefinite(a):
    # A real symmetric matrix is PSD iff every principal minor is >= 0.
    if not hermitian(a):
        return False
    n = len(a)
    return all(
        determinant(principal_submatrix(a, indices)) >= 0
        for k in range(1, n + 1)
        for indices in combinations(range(n), k)
    )


def inverse(a):
    n = len(a)
    aug = [list(a[i]) + list(identity(n)[i]) for i in range(n)]
    for j in range(n):
        pivot = next((i for i in range(j, n) if aug[i][j] != 0), None)
        if pivot is None:
            raise ArithmeticError("Singular matrix")
        aug[j], aug[pivot] = aug[pivot], aug[j]
        divisor = aug[j][j]
        aug[j] = [x / divisor for x in aug[j]]
        for i in range(n):
            if i != j:
                factor = aug[i][j]
                aug[i] = [
                    x - factor * y for x, y in zip(aug[i], aug[j])
                ]
    return tuple(tuple(row[n:]) for row in aug)


def trace(a):
    return sum((a[i][i] for i in range(len(a))), F(0))


def require(condition, message):
    if not condition:
        raise ArithmeticError(message)


def show(name, a):
    print(name + " =")
    for row in a:
        print("  [" + ", ".join(str(x) for x in row) + "]")


counts = {"total": 0, "noncommuting": 0, "singular_Q": 0, "zero_Q": 0}


def check(s, t):
    n = len(s)
    require(len(t) == n, "Dimension mismatch")
    require(positive_definite(s), "Invalid reference-root construction")
    require(positive_semidefinite(t), "Invalid Q-root construction")

    si = inverse(s)
    r = multiply(s, s)
    p = r
    q = multiply(multiply(si, multiply(t, t)), si)
    ri = inverse(r)
    unit = identity(n)

    # Explicitly verify every stated hypothesis, independently of construction.
    require(positive_definite(r), "R is not positive definite")
    require(positive_semidefinite(p), "P is not positive semidefinite")
    require(positive_semidefinite(q), "Q is not positive semidefinite")
    require(p == r, "The required equality P = R failed")

    # Exact certificates identify the unique positive semidefinite roots.
    require(positive_definite(s), "sqrt(R) certificate is not positive")
    require(multiply(s, s) == r, "sqrt(R) certificate failed")

    root_p = r
    root_q = t
    require(positive_semidefinite(root_p), "First root is not PSD")
    require(positive_semidefinite(root_q), "Second root is not PSD")
    require(
        multiply(root_p, root_p) == multiply(multiply(s, p), s),
        "First square-root identity failed",
    )
    require(
        multiply(root_q, root_q) == multiply(multiply(s, q), s),
        "Second square-root identity failed",
    )
    require(multiply(r, ri) == unit, "Inverse certificate failed")
    require(multiply(ri, r) == unit, "Inverse certificate failed")

    generalized = trace(multiply(multiply(root_p, ri), root_q))
    uhlmann = trace(root_q)

    counts["total"] += 1
    counts["noncommuting"] += int(multiply(r, q) != multiply(q, r))
    counts["singular_Q"] += int(determinant(q) == 0)
    counts["zero_Q"] += int(all(x == 0 for row in q for x in row))

    if generalized != uhlmann:
        print("Exact rational counterexample; all hypotheses verified.")
        print("dimension =", n)
        show("P", p)
        show("Q", q)
        show("R", r)
        show("sqrt(R)", s)
        show("sqrt(sqrt(R) P sqrt(R))", root_p)
        show("sqrt(sqrt(R) Q sqrt(R))", root_q)
        print("F_R(R, Q) =", generalized)
        print("F^U(R, Q) =", uhlmann)
        print("Exact difference =", generalized - uhlmann)
        print("VERDICT: COUNTEREXAMPLE_VERIFIED")
        raise SystemExit(0)


# Exhaustive scalar grid, including zero Q and non-normalized references.
for s_value in (F(1, 3), F(1), F(2), F(7, 2)):
    for t_value in (F(0), F(1, 5), F(1), F(3)):
        check(matrix([[s_value]]), matrix([[t_value]]))

# Exhaustive combinations from explicitly specified symmetric 2x2 grids.
s_grid = []
for a, d, b in product(range(1, 4), range(1, 4), range(-1, 2)):
    s = matrix([[a, b], [b, d]])
    if positive_definite(s):
        s_grid.append(s)

t_grid = []
for a, d, b in product(range(3), range(3), range(-2, 3)):
    t = matrix([[a, b], [b, d]])
    if positive_semidefinite(t):
        t_grid.append(t)

for s in s_grid:
    for t in t_grid:
        check(s, t)

# Reproducible 3x3 rational cases with zero, rank-one, and general PSD Q.
rng = random.Random(4004)
for case in range(36):
    a = matrix([[rng.randint(-2, 2) for _ in range(3)] for _ in range(3)])
    gram = multiply(a, transpose(a))
    shift = F(1 + case % 3, 1 + case % 2)
    s = tuple(
        tuple(gram[i][j] + (shift if i == j else F(0)) for j in range(3))
        for i in range(3)
    )

    if case % 3 == 0:
        t = matrix([[0] * 3 for _ in range(3)])
    elif case % 3 == 1:
        v = [F(rng.randint(-3, 3), 2) for _ in range(3)]
        t = matrix([[v[i] * v[j] for j in range(3)] for i in range(3)])
    else:
        b = matrix([
            [F(rng.randint(-3, 3), 2) for _ in range(3)]
            for _ in range(3)
        ])
        t = multiply(b, transpose(b))
    check(s, t)

print("All hypothesis checks and square-root certificates used exact rationals.")
print("Checked", counts["total"], "instances in dimensions 1, 2, and 3.")
print("Exhaustive 2x2 grid:", len(s_grid), "reference roots x",
      len(t_grid), "PSD roots.")
print("Noncommuting R,Q cases:", counts["noncommuting"])
print("Singular Q cases:", counts["singular_Q"])
print("Zero Q cases:", counts["zero_Q"])
print("Both fidelities were exactly equal in every tested instance.")
print("VERDICT: CONSISTENT_NO_COUNTEREXAMPLE")
