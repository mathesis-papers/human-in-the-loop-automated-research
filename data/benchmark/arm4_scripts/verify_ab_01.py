#!/usr/bin/env python3
"""
Test the claimed realignment bound using a rational Horodecki state.

All hypothesis checks and the final violation certificate use exact rational
arithmetic. NumPy is used only to suggest a dual witness. The certificate proves
    ||R(rho)||_1 >= <W, R(rho)> > 1
by checking exactly that ||W||_op <= 1.
"""

from fractions import Fraction as F
import numpy as np


def transpose(A):
    return [list(row) for row in zip(*A)]


def exact_psd(A):
    """Exact PSD test for a real symmetric matrix by Schur complements."""
    n = len(A)
    if any(len(row) != n for row in A):
        return False
    if any(A[i][j] != A[j][i] for i in range(n) for j in range(n)):
        return False

    B = [row[:] for row in A]
    while B:
        m = len(B)
        if any(B[i][i] < 0 for i in range(m)):
            return False

        pivot = next((i for i in range(m) if B[i][i] > 0), None)
        if pivot is None:
            # A PSD matrix with zero diagonal must be the zero matrix.
            return all(x == 0 for row in B for x in row)

        remaining = [i for i in range(m) if i != pivot]
        d = B[pivot][pivot]
        B = [
            [B[i][j] - B[i][pivot] * B[pivot][j] / d
             for j in remaining]
            for i in remaining
        ]
    return True


def partial_transpose_B(rho):
    result = [[F(0) for _ in range(9)] for _ in range(9)]
    for i in range(3):
        for j in range(3):
            for ip in range(3):
                for jp in range(3):
                    result[3 * i + jp][3 * ip + j] = rho[3 * i + j][3 * ip + jp]
    return result


def realignment(rho):
    result = [[F(0) for _ in range(9)] for _ in range(9)]
    for i in range(3):
        for ip in range(3):
            for j in range(3):
                for jp in range(3):
                    result[3 * i + ip][3 * j + jp] = rho[3 * i + j][3 * ip + jp]
    return result


def gram(A):
    n = len(A)
    return [
        [sum((A[k][i] * A[k][j] for k in range(n)), F(0))
         for j in range(n)]
        for i in range(n)
    ]


def max_absolute_row_sum(A):
    return max(sum((abs(x) for x in row), F(0)) for row in A)


def print_matrix(label, A):
    print(label)
    for row in A:
        print("  [" + ", ".join(str(x) for x in row) + "]")


def main():
    # This rational parameter makes the square root rational as well.
    a = F(3, 5)
    root = F(4, 5)
    assert 0 < a < 1
    assert root > 0 and root * root == 1 - a * a

    M = [[F(0) for _ in range(9)] for _ in range(9)]
    diagonal = [a, a, a, a, a, a, (1 + a) / 2, a, (1 + a) / 2]
    for i, value in enumerate(diagonal):
        M[i][i] = value
    for i, j in [(0, 4), (0, 8), (4, 8)]:
        M[i][j] = M[j][i] = a
    M[6][8] = M[8][6] = root / 2

    normalization = 8 * a + 1
    rho = [[value / normalization for value in row] for row in M]

    # Independently check every matrix entry against the stated definition.
    specified_off_diagonal = {
        (0, 4): a,
        (0, 8): a,
        (4, 8): a,
        (6, 8): root / 2,
    }
    for i in range(9):
        for j in range(9):
            expected = (
                diagonal[i] if i == j
                else specified_off_diagonal.get((min(i, j), max(i, j)), F(0))
            )
            assert rho[i][j] == expected / normalization

    assert len(rho) == 9 and all(len(row) == 9 for row in rho)
    assert rho == transpose(rho)  # Real symmetry implies Hermiticity.
    assert sum((rho[i][i] for i in range(9)), F(0)) == 1
    assert exact_psd(rho)

    pt = partial_transpose_B(rho)
    assert exact_psd(pt)

    R = realignment(rho)
    R_float = np.array([[float(x) for x in row] for row in R], dtype=float)
    U, singular_values, Vh = np.linalg.svd(R_float, full_matrices=False)

    # The polar factor suggests a norm-dual certificate. Rationalize it, then
    # scale using an exact upper bound for its squared operator norm.
    denominator = 10**9
    polar = U @ Vh
    B = [
        [F(int(round(float(polar[i, j]) * denominator)), denominator)
         for j in range(9)]
        for i in range(9)
    ]
    g = max_absolute_row_sum(gram(B))
    scale = max(F(1), g)
    W = [[x / scale for x in row] for row in B]

    # For symmetric W^T W, spectral radius <= maximum absolute row sum.
    # Thus this exact check establishes ||W||_op <= 1.
    gram_bound = max_absolute_row_sum(gram(W))
    assert gram_bound <= 1

    pairing = sum(
        (W[i][j] * R[i][j] for i in range(9) for j in range(9)),
        F(0),
    )
    strict_margin = F(1, 10**6)

    if pairing > 1 + strict_margin:
        print("Explicit counterexample: a =", a)
        print("sqrt(1-a^2) =", root)
        print("All entries, normalization, Hermiticity, positivity, and PPT")
        print("were verified with exact rational arithmetic.")
        print_matrix("rho (basis ordered as in the proposition):", rho)
        print_matrix("Exact dual certificate W:", W)
        print("Exact upper bound for ||W||_op^2:", gram_bound)
        print("Exact lower bound for ||R(rho)||_1:", pairing)
        print("Exact certified excess above 1:", pairing - 1)
        print("Certified lower bound (decimal):", format(float(pairing), ".12f"))
        print("Numerical singular-value sum:", format(float(singular_values.sum()), ".12f"))
        print("The certified excess is strictly greater than 1e-6.")
        print("VERDICT: COUNTEREXAMPLE_VERIFIED")
    else:
        print("Checked the exact rational Horodecki state at a=3/5.")
        print("Verified all stated hypotheses, including positivity and PPT.")
        print("No violation exceeding 1e-6 was certified by the dual witness.")
        print("Numerical realignment norm:", format(float(singular_values.sum()), ".12f"))
        print("VERDICT: CONSISTENT_NO_COUNTEREXAMPLE")


if __name__ == "__main__":
    main()
