#!/usr/bin/env python3
"""
Search for a counterexample to the stated generalized Bures-Wasserstein DPI.

All inputs and Kraus operators have rational entries. Before reporting a
counterexample, the script checks every hypothesis exactly with Fraction
arithmetic, and recomputes both distances using 80-digit Decimal arithmetic.
Only violations larger than 1e-6 are accepted.

Dependencies: Python standard library and numpy.
"""

import time
import random
from fractions import Fraction as F
from decimal import Decimal, localcontext

import numpy as np


START = time.monotonic()
SEARCH_SECONDS = 10.0
MAX_TRIALS = 20000
STRICT_MARGIN = Decimal("0.000001")
RNG = random.Random(20261127)

ZERO = F(0)
ONE = F(1)
IDENTITY = [[ONE, ZERO], [ZERO, ONE]]


def transpose(a):
    return [list(row) for row in zip(*a)]


def multiply(a, b):
    return [
        [sum((a[i][k] * b[k][j] for k in range(len(b))), ZERO)
         for j in range(len(b[0]))]
        for i in range(len(a))
    ]


def add(a, b):
    return [[a[i][j] + b[i][j] for j in range(2)] for i in range(2)]


def scale(a, s):
    return [[s * x for x in row] for row in a]


def trace(a):
    return a[0][0] + a[1][1]


def determinant(a):
    return a[0][0] * a[1][1] - a[0][1] * a[1][0]


def symmetric(a):
    return a[0][1] == a[1][0]


def psd(a):
    # Exact necessary and sufficient conditions for a real symmetric 2x2 matrix.
    return (
        symmetric(a)
        and a[0][0] >= 0
        and a[1][1] >= 0
        and determinant(a) >= 0
    )


def pd(a):
    return symmetric(a) and a[0][0] > 0 and determinant(a) > 0


def channel(a, kraus):
    out = [[ZERO, ZERO], [ZERO, ZERO]]
    for k in kraus:
        out = add(out, multiply(multiply(k, a), transpose(k)))
    return out


def verify_hypotheses(p, q, r, kraus):
    assert psd(p) and trace(p) == ONE, "P is not a density matrix"
    assert psd(q) and trace(q) == ONE, "Q is not a density matrix"
    assert pd(r), "R is not positive definite"

    completeness = [[ZERO, ZERO], [ZERO, ZERO]]
    for k in kraus:
        assert len(k) == 2 and all(len(row) == 2 for row in k)
        completeness = add(completeness, multiply(transpose(k), k))
    assert completeness == IDENTITY, "The Kraus channel is not trace preserving"
    # A Kraus representation proves complete positivity exactly.

    pp, qq, rr = (channel(a, kraus) for a in (p, q, r))
    assert psd(pp) and trace(pp) == ONE
    assert psd(qq) and trace(qq) == ONE
    assert pd(rr), "Phi(R) is not positive definite"
    return pp, qq, rr


def random_gram(density=False, require_pd=False):
    while True:
        a, b, c, d = [RNG.randint(-9, 9) for _ in range(4)]
        # Include rank-one density matrices and widely varying reference spectra.
        if density and RNG.randrange(4) == 0:
            b = d = 0
        g = [
            [F(a * a + b * b), F(a * c + b * d)],
            [F(a * c + b * d), F(c * c + d * d)],
        ]
        if require_pd:
            # Strictly positive rational regularization, sometimes very small.
            epsilon = RNG.choice([F(1), F(1, 10), F(1, 1000), F(1, 100000)])
            g[0][0] += epsilon
            g[1][1] += epsilon
        if trace(g) == 0:
            continue
        if require_pd and not pd(g):
            continue
        if density:
            g = scale(g, ONE / trace(g))
        return g


def random_rotation():
    t = F(RNG.randint(-12, 12), RNG.randint(1, 12))
    c = (ONE - t * t) / (ONE + t * t)
    s = 2 * t / (ONE + t * t)
    return [[c, -s], [s, c]]


DAMPING_PAIRS = [
    (F(3, 5), F(4, 5)),
    (F(4, 5), F(3, 5)),
    (F(5, 13), F(12, 13)),
    (F(12, 13), F(5, 13)),
    (F(7, 25), F(24, 25)),
    (F(24, 25), F(7, 25)),
    (F(20, 101), F(99, 101)),
    (F(99, 101), F(20, 101)),
]


def random_channel():
    u, v = random_rotation(), random_rotation()
    if RNG.randrange(3):
        c, s = RNG.choice(DAMPING_PAIRS)
        base = [
            [[ONE, ZERO], [ZERO, c]],
            [[ZERO, s], [ZERO, ZERO]],
        ]
    else:
        # A rational random-unitary channel: c^2 + s^2 = 1.
        c, s = RNG.choice(DAMPING_PAIRS)
        base = [scale(IDENTITY, c), scale(random_rotation(), s)]
    return [multiply(multiply(u, k), v) for k in base]


def as_numpy(a):
    return np.array([[float(x) for x in row] for row in a], dtype=float)


def numeric_sqrt(a):
    a = (a + a.T) * 0.5
    eigenvalues, eigenvectors = np.linalg.eigh(a)
    if eigenvalues[0] < -1e-10:
        raise ArithmeticError("Unexpected negative eigenvalue")
    return (eigenvectors * np.sqrt(np.maximum(eigenvalues, 0.0))) @ eigenvectors.T


def numeric_distance(p, q, r):
    h = numeric_sqrt(r)
    ap = numeric_sqrt(h @ p @ h)
    aq = numeric_sqrt(h @ q @ h)
    fidelity = np.trace(ap @ np.linalg.solve(r, aq))
    return float(np.trace(p + q) - 2.0 * fidelity)


def decimal_matrix(a):
    return [
        [Decimal(x.numerator) / Decimal(x.denominator) for x in row]
        for row in a
    ]


def dmultiply(a, b):
    return [
        [sum((a[i][k] * b[k][j] for k in range(2)), Decimal(0))
         for j in range(2)]
        for i in range(2)
    ]


def dtrace(a):
    return a[0][0] + a[1][1]


def dinverse(a):
    det = a[0][0] * a[1][1] - a[0][1] * a[1][0]
    assert det > 0
    return [
        [a[1][1] / det, -a[0][1] / det],
        [-a[1][0] / det, a[0][0] / det],
    ]


def dsqrt(a):
    # For positive semidefinite 2x2 A:
    # sqrt(A) = (A + sqrt(det(A))*I) / sqrt(tr(A)+2*sqrt(det(A))).
    offdiag = (a[0][1] + a[1][0]) / 2
    a = [[a[0][0], offdiag], [offdiag, a[1][1]]]
    det = a[0][0] * a[1][1] - offdiag * offdiag
    if det < 0:
        # Exact PSD is checked separately; allow only Decimal roundoff.
        assert abs(det) < Decimal("1e-60")
        det = Decimal(0)
    rootdet = det.sqrt()
    denominator = (dtrace(a) + 2 * rootdet).sqrt()
    if denominator == 0:
        return [[Decimal(0), Decimal(0)], [Decimal(0), Decimal(0)]]
    return [
        [(a[0][0] + rootdet) / denominator, offdiag / denominator],
        [offdiag / denominator, (a[1][1] + rootdet) / denominator],
    ]


def decimal_distance(p, q, r):
    p, q, r = map(decimal_matrix, (p, q, r))
    h = dsqrt(r)
    ap = dsqrt(dmultiply(dmultiply(h, p), h))
    aq = dsqrt(dmultiply(dmultiply(h, q), h))
    fidelity = dtrace(dmultiply(dmultiply(ap, dinverse(r)), aq))
    return dtrace(p) + dtrace(q) - 2 * fidelity


def print_matrix(name, a):
    print(name + " = [")
    for row in a:
        print("  [" + ", ".join(str(x) for x in row) + "],")
    print("]")


def main():
    tested = 0
    numerical_candidates = 0

    while tested < MAX_TRIALS and time.monotonic() - START < SEARCH_SECONDS:
        p = random_gram(density=True)
        q = random_gram(density=True)
        r = random_gram(require_pd=True)
        kraus = random_channel()

        # Verify every tested instance using exact rational arithmetic.
        pp, qq, rr = verify_hypotheses(p, q, r, kraus)
        tested += 1

        try:
            before = numeric_distance(*map(as_numpy, (p, q, r)))
            after = numeric_distance(*map(as_numpy, (pp, qq, rr)))
        except (ArithmeticError, np.linalg.LinAlgError):
            continue

        if not np.isfinite(before + after) or after - before <= 2e-6:
            continue

        numerical_candidates += 1
        with localcontext() as ctx:
            ctx.prec = 80
            exact_pp, exact_qq, exact_rr = verify_hypotheses(p, q, r, kraus)
            high_before = decimal_distance(p, q, r)
            high_after = decimal_distance(exact_pp, exact_qq, exact_rr)
            gap = high_after - high_before

            if gap <= STRICT_MARGIN:
                continue

            # Independently repeat at higher precision to reject unstable values.
            ctx.prec = 110
            check_before = decimal_distance(p, q, r)
            check_after = decimal_distance(exact_pp, exact_qq, exact_rr)
            check_gap = check_after - check_before
            if abs(check_gap - gap) > Decimal("1e-40"):
                continue
            if check_gap <= STRICT_MARGIN:
                continue

            print("Explicit counterexample with n = 2 and real rational entries.")
            print("Phi(X) = sum_j K_j X K_j^T.")
            print_matrix("P", p)
            print_matrix("Q", q)
            print_matrix("R", r)
            for j, k in enumerate(kraus):
                print_matrix("K_" + str(j), k)
            print_matrix("Phi(P)", exact_pp)
            print_matrix("Phi(Q)", exact_qq)
            print_matrix("Phi(R)", exact_rr)
            print("Exact hypothesis verification:")
            print("P and Q are Hermitian PSD and each has trace exactly 1.")
            print("R and Phi(R) are positive definite by exact principal minors.")
            print("The rational Kraus operators satisfy sum_j K_j^T K_j = I exactly.")
            print("Thus Phi is completely positive and trace preserving.")
            print("B_R(P,Q) =", format(check_before, ".55g"))
            print("B_Phi(R)(Phi(P),Phi(Q)) =", format(check_after, ".55g"))
            print("Output distance minus input distance =", format(check_gap, ".55g"))
            print("The violation exceeds 1e-6 and agrees at 80 and 110 digits.")
            print("Tested instances:", tested)
            print("VERDICT: COUNTEREXAMPLE_VERIFIED")
            return

    print(
        "Checked %d exact rational 2x2 instances with density matrices P,Q, "
        "positive definite R, and rational CPTP Kraus channels. "
        "Channels included rotated amplitude-damping and random-unitary channels. "
        "%d numerical candidates received high-precision examination. "
        "No verified violation larger than 1e-6 was found; this finite search "
        "does not prove the universal proposition."
        % (tested, numerical_candidates)
    )
    print("VERDICT: CONSISTENT_NO_COUNTEREXAMPLE")


if __name__ == "__main__":
    main()
