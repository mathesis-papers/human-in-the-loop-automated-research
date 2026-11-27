#!/usr/bin/env python3
"""
Exhaustively test the proposition for every odd modulus 3 <= m <= 101,
every subgroup of its unit group containing -1, and every unit coset.

All mathematical checks use exact integer arithmetic.
A time budget permits a clean exit if execution is unusually slow.
"""

from math import gcd
from time import monotonic


MAX_MODULUS = 101
TIME_BUDGET_SECONDS = 12.0


def require(condition, message):
    if not condition:
        raise ArithmeticError(message)


def adjoin_generator(m, subgroup, generator):
    """Return <subgroup, generator> using exact modular multiplication."""
    generated = set(subgroup)
    power = generator % m
    while power not in subgroup:
        generated.update((power * h) % m for h in subgroup)
        power = (power * generator) % m
    return frozenset(generated)


def verify_hypotheses(m, subgroup, units):
    """Independently verify every hypothesis concerning m and H."""
    require(isinstance(m, int) and m >= 3 and m % 2 == 1,
            "Modulus must be an odd integer at least 3.")
    require(bool(subgroup), "A subgroup must be nonempty.")
    require(subgroup <= units, "Every subgroup element must be a unit.")
    require(1 in subgroup, "The identity must belong to H.")
    require(m - 1 in subgroup, "-1 modulo m must belong to H.")

    for a in subgroup:
        require(1 <= a < m and gcd(a, m) == 1,
                "Invalid least positive unit representative.")
        require(any((a * b) % m == 1 for b in subgroup),
                "An element has no inverse in H.")
        for b in subgroup:
            require((a * b) % m in subgroup,
                    "H is not closed under multiplication.")


def main():
    started = monotonic()
    completed_moduli = []
    subgroup_checks = 0
    coset_checks = 0
    budget_exhausted = False

    for m in range(3, MAX_MODULUS + 1, 2):
        if monotonic() - started >= TIME_BUDGET_SECONDS:
            budget_exhausted = True
            break

        units = frozenset(a for a in range(1, m) if gcd(a, m) == 1)

        # Starting with <-1>, repeatedly adjoin every possible unit.
        # This enumerates all subgroups containing -1: every such subgroup
        # can be reached by adjoining its elements one at a time.
        initial = frozenset((1, m - 1))
        seen = {initial}
        pending = [initial]
        modulus_complete = True

        while pending:
            if monotonic() - started >= TIME_BUDGET_SECONDS:
                budget_exhausted = True
                modulus_complete = False
                break

            subgroup = pending.pop()
            verify_hypotheses(m, subgroup, units)
            subgroup_checks += 1

            for c in sorted(units):
                require(1 <= c < m and gcd(c, m) == 1,
                        "The coset multiplier must be a unit.")
                coset = frozenset((c * h) % m for h in subgroup)
                require(len(coset) == len(subgroup),
                        "Multiplication by a unit must preserve cardinality.")
                require(all(1 <= x < m and gcd(x, m) == 1 for x in coset),
                        "Invalid least positive coset representative.")

                residue_sum = sum(coset)
                coset_checks += 1

                # Avoid division: this is exactly S_m(cH) != m*|H|/2.
                if 2 * residue_sum != m * len(subgroup):
                    # Recheck all hypotheses immediately before reporting.
                    verify_hypotheses(m, subgroup, units)
                    require(c in units, "Witness multiplier is not a unit.")
                    require(coset == frozenset((c * h) % m for h in subgroup),
                            "Witness coset is incorrect.")
                    require(2 * sum(coset) != m * len(subgroup),
                            "Witness does not violate the conclusion.")

                    print("Explicit counterexample; all hypotheses verified exactly.")
                    print("m =", m)
                    print("H =", sorted(subgroup))
                    print("c =", c)
                    print("Least positive representatives of cH =", sorted(coset))
                    print("|H| =", len(subgroup))
                    print("S_m(cH) =", residue_sum)
                    print("2*S_m(cH) =", 2 * residue_sum)
                    print("m*|H| =", m * len(subgroup))
                    print("VERDICT: COUNTEREXAMPLE_VERIFIED")
                    return

            for generator in sorted(units - subgroup):
                larger = adjoin_generator(m, subgroup, generator)
                if larger not in seen:
                    seen.add(larger)
                    pending.append(larger)

        if modulus_complete:
            completed_moduli.append(m)
        else:
            break

    print("All tested instances satisfy the conclusion using exact arithmetic.")
    print("Independently verified subgroup hypotheses for", subgroup_checks,
          "subgroups; checked", coset_checks, "unit multipliers.")
    if completed_moduli:
        print("Exhaustively checked every eligible subgroup and every unit "
              "multiplier for every odd modulus from 3 through",
              completed_moduli[-1], "(inclusive).")
    if budget_exhausted:
        print("Stopped at the time budget; any unfinished modulus is excluded "
              "from the exhaustive range.")
    print("Finite testing does not establish the claim for untested moduli.")
    print("VERDICT: CONSISTENT_NO_COUNTEREXAMPLE")


if __name__ == "__main__":
    main()
