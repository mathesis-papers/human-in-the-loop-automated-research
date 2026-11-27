#!/usr/bin/env python3
"""
Search for an exact counterexample to:
    If a cyclic subgroup H of even order in (Z/pqZ)^* has residue
    sum pq*|H|/2, then every unit coset of H has the same sum.

All mathematical checks use integers. No floating-point tolerances are needed.
The search is deterministic, checks each distinct cyclic subgroup once, and
stops after a bounded search or a conservative wall-clock budget.
"""

import math
import time


def is_prime(n):
    if n < 2:
        return False
    if n % 2 == 0:
        return n == 2
    return all(n % d != 0 for d in range(3, math.isqrt(n) + 1, 2))


def generated_subgroup(a, m):
    """Return the exact powers of the unit a up to its first return to 1."""
    if math.gcd(a, m) != 1:
        raise ValueError("The proposed generator is not a unit.")
    powers = []
    x = 1
    while True:
        powers.append(x)
        x = (x * a) % m
        if x == 1:
            return frozenset(powers)
        if len(powers) >= m:
            raise RuntimeError("Unexpected failure to close a unit subgroup.")


def verify_witness(p, q, a, c, proposed_h):
    """Independently check every stated hypothesis and the strict failure."""
    m = p * q
    if not (is_prime(p) and is_prime(q) and p != q):
        return None
    if not (p > 2 and q > 2 and p % 2 == 1 and q % 2 == 1):
        return None
    if not (1 <= a < m and math.gcd(a, m) == 1):
        return None
    if not (1 <= c < m and math.gcd(c, m) == 1):
        return None

    h = generated_subgroup(a, m)
    if h != proposed_h:
        return None
    k = len(h)
    if k == 0 or k % 2 != 0:
        return None
    if not all(1 <= x < m and math.gcd(x, m) == 1 for x in h):
        return None

    # The power enumeration gives cyclicity. Also verify subgroup closure
    # efficiently: multiplication by a permutes H, and 1 belongs to H.
    if 1 not in h or frozenset((a * x) % m for x in h) != h:
        return None
    if pow(a, k, m) != 1:
        return None
    if any(pow(a, j, m) == 1 for j in range(1, k)):
        return None

    # Integer comparison avoids even an intermediate division.
    if 2 * sum(h) != m * k:
        return None

    coset = frozenset((c * x) % m for x in h)
    if len(coset) != k:
        return None
    if not all(1 <= x < m and math.gcd(x, m) == 1 for x in coset):
        return None
    if 2 * sum(coset) == m * k:
        return None

    return h, coset, k


def main():
    start = time.monotonic()
    budget_seconds = 10.0
    primes = [n for n in range(3, 98, 2) if is_prime(n)]
    pairs = sorted(
        ((p, q) for i, p in enumerate(primes) for q in primes[i + 1:]),
        key=lambda pair: (pair[0] * pair[1], pair),
    )

    completed_moduli = 0
    distinct_subgroups = 0
    centered_even_subgroups = 0
    cosets_checked = 0
    timed_out = False

    for p, q in pairs:
        if time.monotonic() - start >= budget_seconds:
            timed_out = True
            break

        m = p * q
        units = [x for x in range(1, m) if math.gcd(x, m) == 1]
        unit_set = set(units)
        seen = set()
        modulus_complete = True

        for a in units:
            if time.monotonic() - start >= budget_seconds:
                timed_out = True
                modulus_complete = False
                break

            h = generated_subgroup(a, m)
            if h in seen:
                continue
            seen.add(h)
            distinct_subgroups += 1

            k = len(h)
            if k % 2 or 2 * sum(h) != m * k:
                continue
            centered_even_subgroups += 1

            # These exact cosets partition the whole unit group.
            remaining = unit_set.copy()
            while remaining:
                if time.monotonic() - start >= budget_seconds:
                    timed_out = True
                    modulus_complete = False
                    break

                c = min(remaining)
                coset = frozenset((c * x) % m for x in h)
                cosets_checked += 1

                if 2 * sum(coset) != m * k:
                    verified = verify_witness(p, q, a, c, h)
                    if verified is None:
                        raise RuntimeError("Candidate failed independent verification.")

                    verified_h, verified_coset, verified_k = verified
                    target = m * verified_k // 2
                    print("Exact counterexample; every hypothesis verified.")
                    print(f"Distinct odd primes: p={p}, q={q}; m=p*q={m}")
                    print(f"Unit generator a={a}; gcd(a,m)={math.gcd(a, m)}")
                    print(f"H=<a>={sorted(verified_h)}")
                    print(f"Exact order k={verified_k}, which is even")
                    print(f"S_m(H)={sum(verified_h)} = m*k/2={target}")
                    print(f"Unit c={c}; gcd(c,m)={math.gcd(c, m)}")
                    print(f"cH={sorted(verified_coset)}")
                    print(f"S_m(cH)={sum(verified_coset)}")
                    print(f"Exact nonzero deviation: {sum(verified_coset) - target}")
                    print("VERDICT: COUNTEREXAMPLE_VERIFIED")
                    return

                remaining.difference_update(coset)

            if not modulus_complete:
                break

        if modulus_complete:
            completed_moduli += 1
        if timed_out:
            break

    print("No valid counterexample found in the tested instances.")
    print("Search domain: products of two distinct odd primes at most 97,")
    print("ordered by product; all calculations used exact integer arithmetic.")
    print(f"Moduli completely exhausted: {completed_moduli}")
    print(f"Distinct cyclic subgroups checked: {distinct_subgroups}")
    print(f"Centered even-order subgroups found: {centered_even_subgroups}")
    print(f"Individual cosets checked: {cosets_checked}")
    print("Search stopped at the time budget." if timed_out
          else "The entire stated finite search domain was exhausted.")
    print("VERDICT: CONSISTENT_NO_COUNTEREXAMPLE")


if __name__ == "__main__":
    main()
