#!/usr/bin/env python3
"""Exact, bounded verification of blinded claim ab_13."""
from fractions import Fraction
from math import comb, isqrt


def main():
    coefficient_count = 600
    evaluation_terms = 180
    scale = 10 ** 90
    strict_gap = Fraction(1, 10 ** 6)

    # Independently generate the coefficients c_j of (1 - 4z)^(-1/2).
    # The analytic function with constant coefficient 1 satisfies
    # (1 - 4z) C'(z) = 2 C(z), hence
    # c_{j+1} = 2(2j+1)c_j/(j+1).
    rhs_central = Fraction(1)
    lhs_partial = 0
    rhs_partial = Fraction(0)

    for n in range(1, coefficient_count + 1):
        assert isinstance(n, int) and n >= 1
        lhs_partial += comb(2 * (n - 1), n - 1)
        rhs_partial += rhs_central

        # Multiplication by z/(1-z) makes rhs_partial the coefficient
        # of z^n in the claimed closed form.
        if lhs_partial != rhs_partial:
            print("Exact coefficient mismatch:")
            print("n =", n)
            print("a_n from the stated definition =", lhs_partial)
            print("coefficient of the claimed analytic closed form =", rhs_partial)
            print("Uniqueness of Taylor coefficients disproves the identity.")
            print("VERDICT: COUNTEREXAMPLE_VERIFIED")
            return

        rhs_central *= Fraction(2 * (2 * (n - 1) + 1), n)

    def sqrt_enclosure(q):
        """Return rational lower/upper bounds for the positive sqrt(q)."""
        assert q > 0
        k = isqrt((q.numerator * scale * scale) // q.denominator)
        lower = Fraction(k, scale)
        upper = Fraction(k + 1, scale)
        assert 0 <= lower and lower * lower <= q < upper * upper
        return lower, upper

    def lhs_enclosure(z):
        """Enclose the infinite defining series using an exact tail bound."""
        assert isinstance(z, Fraction) and abs(z) < Fraction(1, 4)
        total = Fraction(0)
        power = z
        partial = 0
        for n in range(1, evaluation_terms + 1):
            partial += comb(2 * (n - 1), n - 1)
            total += partial * power
            power *= z

        # Since binom(2j,j) <= 4^j,
        # a_n <= sum_{j=0}^{n-1}4^j < 4^n/3.
        # Thus the absolute tail beyond N is at most
        # (4|z|)^(N+1)/(3(1-4|z|)).
        ratio = 4 * abs(z)
        tail = ratio ** (evaluation_terms + 1) / (3 * (1 - ratio))
        assert tail >= 0
        return total - tail, total + tail

    def rhs_enclosure(z):
        """Enclose z/((1-z)*sqrt(1-4z)) using exact rationals."""
        assert isinstance(z, Fraction) and abs(z) < Fraction(1, 4)
        radicand = 1 - 4 * z
        assert radicand > 0 and 1 - z > 0
        lower_sqrt, upper_sqrt = sqrt_enclosure(radicand)
        assert lower_sqrt > 0
        factor = z / (1 - z)
        endpoints = (factor / lower_sqrt, factor / upper_sqrt)
        return min(endpoints), max(endpoints)

    points = [
        Fraction(0),
        Fraction(1, 100),
        Fraction(-1, 100),
        Fraction(1, 8),
        Fraction(-1, 8),
        Fraction(1, 5),
        Fraction(-1, 5),
        Fraction(6, 25),
        Fraction(-6, 25),
    ]

    for z in points:
        # These instances satisfy the full stated domain exactly.
        assert abs(z) < Fraction(1, 4)
        lhs_lo, lhs_hi = lhs_enclosure(z)
        rhs_lo, rhs_hi = rhs_enclosure(z)

        # Disjoint certified enclosures with separation > 10^-6
        # rigorously establish a strict violation.
        gap = max(rhs_lo - lhs_hi, lhs_lo - rhs_hi)
        if gap > strict_gap:
            print("Certified counterexample at the exact real point z =", z)
            print("Domain verified exactly: |z| < 1/4.")
            print("Defining series lies in [", lhs_lo, ",", lhs_hi, "]")
            print("Claimed closed form lies in [", rhs_lo, ",", rhs_hi, "]")
            print("Certified separation =", gap, "> 1/1000000")
            print("VERDICT: COUNTEREXAMPLE_VERIFIED")
            return

    print(
        f"Exactly matched the first {coefficient_count} Taylor coefficients, "
        "using binomial integers for the definition and an independent "
        "differential recurrence for the claimed closed form."
    )
    print(
        f"Tested {len(points)} rational points strictly inside |z| < 1/4 "
        f"with {evaluation_terms}-term sums, rigorous geometric tail bounds, "
        "and rational square-root enclosures."
    )
    print("Finite tests found no counterexample; they do not alone prove the identity.")
    print("VERDICT: CONSISTENT_NO_COUNTEREXAMPLE")


if __name__ == "__main__":
    main()
