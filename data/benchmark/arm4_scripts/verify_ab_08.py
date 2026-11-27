#!/usr/bin/env python3
"""Exact verification of blinded claim ab_08 using rational arithmetic."""

from fractions import Fraction


def polynomial_add(a, b):
    """Add polynomials whose coefficients are ordered by increasing degree."""
    result = [0] * max(len(a), len(b))
    for i, coefficient in enumerate(a):
        result[i] += coefficient
    for i, coefficient in enumerate(b):
        result[i] += coefficient
    return result


def polynomial_scale(a, scalar):
    return [scalar * coefficient for coefficient in a]


def polynomial_multiply(a, b):
    result = [0] * (len(a) + len(b) - 1)
    for i, first in enumerate(a):
        for j, second in enumerate(b):
            result[i + j] += first * second
    return result


def report_counterexample(r, u, reciprocal_u, failures):
    # Recheck the sole hypothesis and all reported violations exactly.
    if not isinstance(r, Fraction) or not r > 0:
        raise RuntimeError("Candidate does not satisfy the hypothesis r > 0.")

    denominator = 1 + r + r * r
    if denominator <= 0:
        raise RuntimeError("Unexpected nonpositive denominator.")

    exact_u = r / denominator
    reciprocal = 1 / r
    exact_reciprocal_u = reciprocal / (
        1 + reciprocal + reciprocal * reciprocal
    )
    actual_failures = []
    if exact_u <= 0:
        actual_failures.append("U_r > 0")
    if exact_u > Fraction(1, 3):
        actual_failures.append("U_r <= 1/3")
    if (exact_u == Fraction(1, 3)) != (r == 1):
        actual_failures.append("U_r = 1/3 if and only if r = 1")
    if exact_u != exact_reciprocal_u:
        actual_failures.append("U_r = U_(1/r)")

    if not actual_failures or actual_failures != failures:
        raise RuntimeError("Candidate counterexample failed exact revalidation.")
    if u != exact_u or reciprocal_u != exact_reciprocal_u:
        raise RuntimeError("Inconsistent witness values.")

    print("Exact rational counterexample; all arithmetic is exact.")
    print(f"r = {r}")
    print(f"Hypothesis verified: r > 0 is {r > 0}")
    print(f"1 + r + r^2 = {denominator}")
    print(f"U_r = {exact_u}")
    print(f"1/r = {reciprocal}")
    print(f"U_(1/r) = {exact_reciprocal_u}")
    print(f"1/3 - U_r = {Fraction(1, 3) - exact_u}")
    print("Violated conclusions: " + "; ".join(actual_failures))
    print("VERDICT: COUNTEREXAMPLE_VERIFIED")


def main():
    # Exact polynomial certificates, valid for real r as well as rational r.
    # Coefficient order: constant, r, r^2, ...
    denominator_polynomial = [1, 1, 1]
    r_polynomial = [0, 1]
    r_minus_one = [-1, 1]

    # D - 3r = (r - 1)^2 establishes the claimed bound and equality case,
    # since D = 1 + r + r^2 > 0 whenever r > 0.
    gap_numerator = polynomial_add(
        denominator_polynomial, polynomial_scale(r_polynomial, -3)
    )
    square = polynomial_multiply(r_minus_one, r_minus_one)
    if gap_numerator != square:
        raise RuntimeError("Exact bound certificate failed.")

    # Clearing the positive factor r^2 in U_(1/r) gives numerator r
    # and denominator r^2 + r + 1, which equals D coefficient by coefficient.
    reciprocal_denominator_after_clearing = list(
        reversed(denominator_polynomial)
    )
    if reciprocal_denominator_after_clearing != denominator_polynomial:
        raise RuntimeError("Exact reciprocal-symmetry certificate failed.")

    candidates = {
        Fraction(numerator, denominator)
        for numerator in range(1, 97)
        for denominator in range(1, 97)
    }

    # Include extreme scales and exact perturbations on both sides of r = 1.
    for base in (2, 3, 10):
        for exponent in range(1, 81):
            power = base ** exponent
            candidates.add(Fraction(power))
            candidates.add(Fraction(1, power))
            candidates.add(Fraction(power - 1, power))
            candidates.add(Fraction(power + 1, power))
            candidates.add(Fraction(power, power - 1))
            candidates.add(Fraction(power, power + 1))

    checked = 0
    for r in sorted(candidates):
        # Strictly validate every hypothesis before testing the conclusion.
        if not isinstance(r, Fraction) or r <= 0:
            raise RuntimeError("Invalid test instance.")
        denominator = 1 + r + r * r
        if denominator <= 0:
            raise RuntimeError("Invalid denominator.")

        u = r / denominator
        reciprocal = 1 / r
        reciprocal_u = reciprocal / (1 + reciprocal + reciprocal * reciprocal)

        failures = []
        if u <= 0:
            failures.append("U_r > 0")
        if u > Fraction(1, 3):
            failures.append("U_r <= 1/3")
        if (u == Fraction(1, 3)) != (r == 1):
            failures.append("U_r = 1/3 if and only if r = 1")
        if u != reciprocal_u:
            failures.append("U_r = U_(1/r)")

        if failures:
            report_counterexample(r, u, reciprocal_u, failures)
            return
        checked += 1

    print(f"Checked {checked} distinct positive rational instances exactly.")
    print("Exhausted all r = p/q with 1 <= p,q <= 96.")
    print("Also checked extreme scales and perturbations around r = 1.")
    print("Verified positivity, the upper bound, both directions of the")
    print("equality characterization, and reciprocal symmetry on every instance.")
    print("Exact polynomial certificates also establish the real-domain claims:")
    print("D - 3r = (r - 1)^2 and r^2 D(1/r) = D(r).")
    print("For real r > 0, D > 0; the square vanishes exactly at r = 1.")
    print("VERDICT: CONSISTENT_NO_COUNTEREXAMPLE")


if __name__ == "__main__":
    main()
