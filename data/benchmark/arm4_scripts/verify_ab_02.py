#!/usr/bin/env python3
"""
Systematically test the stated two-deletion entropy maximization claim.

For fixed L, write m_y(x) for the number of two-position deletion masks
taking x to y. Every posterior has the same normalizing constant

    T = 4 * binomial(L + 2, 2).

Consequently,
    H(X | Y=y) = log2(T) - log2(P_y) / T,
    P_y = product_x m_y(x)**m_y(x).

Thus arbitrary-precision INTEGER comparisons of P_y decide entropy
comparisons exactly, with no floating-point tolerance or logarithmic
rounding involved. A nonalternating word with P_y <= P_alternating
disproves the claim, including its asserted uniqueness.

The search has a wall-clock budget. Any reported witness is independently
reconstructed using strings and verified with exact rational arithmetic.
"""
import itertools
import math
import time
from collections import Counter
from fractions import Fraction

START = time.perf_counter()
SEARCH_DEADLINE = START + 10.0
MAX_L = 16


def alternating_word(length, first="0"):
    return "".join(str((int(first) + i) % 2) for i in range(length))


def insertion_parameters(length):
    """Bit positions are numbered from the least significant bit."""
    n = length + 2
    params = []
    for i in range(n - 1):
        low_mask = (1 << i) - 1
        for j in range(i + 1, n):
            middle_mask = ((1 << (j - 1)) - 1) ^ low_mask
            params.append((i, j, low_mask, middle_mask, 1 << i, 1 << j))
    return params


def multiplicities_fast(word_integer, params):
    """Enumerate every insertion mask and its four possible inserted bits."""
    counts = {}
    for i, j, low_mask, middle_mask, bit_i, bit_j in params:
        base = (
            (word_integer & low_mask)
            | ((word_integer & middle_mask) << 1)
            | ((word_integer >> (j - 1)) << (j + 1))
        )
        for x in (base, base | bit_i, base | bit_j, base | bit_i | bit_j):
            counts[x] = counts.get(x, 0) + 1
    return counts


POWER_CACHE = {}


def exact_entropy_product(counts):
    histogram = Counter(counts.values())
    product = 1
    for multiplicity, frequency in histogram.items():
        if multiplicity not in POWER_CACHE:
            POWER_CACHE[multiplicity] = pow(multiplicity, multiplicity)
        product *= pow(POWER_CACHE[multiplicity], frequency)
    return product


def independently_verified_distribution(y, fast_counts):
    """
    Independently reconstruct the entire support using string insertion,
    then explicitly enumerate all deletion masks of every support word.

    Completeness follows because every x deleting to y is reconstructed by
    inserting the deleted bits at exactly their original two positions.
    """
    L = len(y)
    n = L + 2
    masks = list(itertools.combinations(range(n), 2))
    assert L >= 1
    assert set(y) <= {"0", "1"}
    assert len(masks) == math.comb(n, 2)

    reconstructed = Counter()
    for i, j in masks:
        for a, b in itertools.product("01", repeat=2):
            source = iter(y)
            chars = []
            for position in range(n):
                if position == i:
                    chars.append(a)
                elif position == j:
                    chars.append(b)
                else:
                    chars.append(next(source))
            assert next(source, None) is None
            reconstructed["".join(chars)] += 1

    explicit = {}
    for x, insertion_count in reconstructed.items():
        assert len(x) == n and set(x) <= {"0", "1"}
        deletion_count = 0
        for i, j in masks:
            output = x[:i] + x[i + 1:j] + x[j + 1:]
            if output == y:
                deletion_count += 1
        assert deletion_count == insertion_count
        assert deletion_count > 0
        explicit[x] = deletion_count

    expected_fast = {int(x, 2): m for x, m in explicit.items()}
    assert expected_fast == fast_counts

    T = 4 * math.comb(n, 2)
    assert sum(explicit.values()) == T

    # Exactly the experiment in the proposition:
    # X is uniform on all 2**n binary words; each of the C(n,2) masks
    # is independently chosen with equal probability.
    px = Fraction(1, 2**n)
    pmask = Fraction(1, len(masks))
    assert px > 0 and pmask > 0
    assert px * (2**n) == 1
    assert pmask * len(masks) == 1

    py = sum((px * pmask * m for m in explicit.values()), Fraction(0))
    assert py == Fraction(1, 2**L)
    posterior = {
        x: (px * pmask * m) / py for x, m in explicit.items()
    }
    assert sum(posterior.values(), Fraction(0)) == 1
    assert all(p > 0 for p in posterior.values())
    assert all(posterior[x] == Fraction(m, T) for x, m in explicit.items())

    product = exact_entropy_product(explicit)
    entropy = -math.fsum(float(p) * math.log2(float(p))
                         for p in posterior.values())
    return explicit, product, entropy, T


def report_witness(L, y, alt, candidate_counts, alt_counts):
    candidate, pc, hc, T = independently_verified_distribution(
        y, candidate_counts
    )
    reference, pa, ha, reference_T = independently_verified_distribution(
        alt, alt_counts
    )
    other_alt = alternating_word(L, "1")

    assert T == reference_T
    assert len(y) == len(alt) == len(other_alt) == L
    assert y not in (alt, other_alt)
    assert any(y[i] == y[i + 1] for i in range(L - 1))
    assert pc <= pa

    # Complementation bijects binary input words and preserves every
    # deletion mask, so both alternating words have the same product.
    complemented_reference = {
        "".join("1" if bit == "0" else "0" for bit in x): m
        for x, m in reference.items()
    }
    other_counts = multiplicities_fast(
        int(other_alt, 2), insertion_parameters(L)
    )
    assert {int(x, 2): m for x, m in complemented_reference.items()} == other_counts
    assert exact_entropy_product(other_counts) == pa

    print("Explicit counterexample to the stated proposition:")
    print("L =", L)
    print("Nonalternating output y =", y)
    print("Alternating outputs =", alt, "and", other_alt)
    print("Input length =", L + 2)
    print("Uniform deletion-mask count =", math.comb(L + 2, 2))
    print("Exact posterior denominator T =", T)
    print("All hypotheses checked by exact integer/rational arithmetic.")
    print("Candidate multiplicity histogram (m: number of inputs):",
          dict(sorted(Counter(candidate.values()).items())))
    print("Alternating multiplicity histogram (m: number of inputs):",
          dict(sorted(Counter(reference.values()).items())))
    print("Exact candidate entropy product P_y =", pc)
    print("Exact alternating entropy product P_alt =", pa)
    print("H(X | Y=y), approximate bits =", format(hc, ".15g"))
    print("H(X | Y=alternating), approximate bits =", format(ha, ".15g"))
    if pc < pa:
        print("Exact inequality: P_y < P_alt, hence H_y > H_alt.")
    else:
        print("Exact equality: P_y = P_alt, hence H_y = H_alt.")
        print("This contradicts the assertion that only the two alternating")
        print("words attain the maximum: either they are not maxima, or")
        print("this nonalternating word is an additional maximizer.")
    print("Complete candidate support, with exact posterior probabilities:")
    for x in sorted(candidate):
        m = candidate[x]
        print("  x =", x, "multiplicity =", m,
              "P(X=x | Y=y) =", str(Fraction(m, T)))
    print("VERDICT: COUNTEREXAMPLE_VERIFIED")


def main():
    checked_outputs = 0
    complete_lengths = []
    partial_length = None

    for L in range(1, MAX_L + 1):
        if time.perf_counter() >= SEARCH_DEADLINE:
            break

        params = insertion_parameters(L)
        alt = alternating_word(L)
        other_alt = alternating_word(L, "1")
        alt_integer = int(alt, 2)
        other_alt_integer = int(other_alt, 2)
        alt_counts = multiplicities_fast(alt_integer, params)
        T = 4 * math.comb(L + 2, 2)
        assert sum(alt_counts.values()) == T
        alt_product = exact_entropy_product(alt_counts)

        finished = True
        for value in range(1 << L):
            if time.perf_counter() >= SEARCH_DEADLINE:
                partial_length = L
                finished = False
                break

            counts = multiplicities_fast(value, params)
            assert sum(counts.values()) == T
            assert all(isinstance(m, int) and m > 0
                       for m in counts.values())
            product = exact_entropy_product(counts)
            checked_outputs += 1

            if value not in (alt_integer, other_alt_integer):
                if product <= alt_product:
                    y = format(value, "0{}b".format(L))
                    report_witness(L, y, alt, counts, alt_counts)
                    return
            else:
                assert product == alt_product

        if finished:
            complete_lengths.append(L)
        else:
            break

    print("Systematic exact two-deletion entropy comparison completed.")
    print("Fully exhausted lengths:", complete_lengths)
    print("Total concrete output words checked:", checked_outputs)
    if partial_length is not None:
        print("Also checked an initial portion of length", partial_length)
    print("Every tested posterior had exact total multiplicity 4*C(L+2,2).")
    print("Entropy ordering was compared using arbitrary-precision integers.")
    print("No counterexample was found in the tested instances.")
    print("These finite checks do not prove the claim for all lengths.")
    print("VERDICT: CONSISTENT_NO_COUNTEREXAMPLE")


if __name__ == "__main__":
    main()
