#!/usr/bin/env python3
"""Exactly test the claimed exclusivity of alternating maximizers."""

from itertools import combinations, product


def is_binary_word(word, length):
    return (
        isinstance(length, int)
        and length >= 0
        and isinstance(word, str)
        and len(word) == length
        and all(bit in "01" for bit in word)
    )


def is_alternating(word):
    return all(word[i] != word[i + 1] for i in range(len(word) - 1))


def two_deletion_subsequences(word):
    """Every length-(L-2) subsequence arises by deleting exactly two positions."""
    return {
        "".join(
            bit for k, bit in enumerate(word)
            if k != i and k != j
        )
        for i, j in combinations(range(len(word)), 2)
    }


def is_subsequence(candidate, word):
    """Independent exact subsequence-membership check."""
    position = 0
    for bit in word:
        if position < len(candidate) and candidate[position] == bit:
            position += 1
    return position == len(candidate)


def independently_count_subsequences(word):
    """Enumerate all possible target words instead of deletion positions."""
    target_length = len(word) - 2
    return {
        "".join(bits)
        for bits in product("01", repeat=target_length)
        if is_subsequence("".join(bits), word)
    }


def main():
    tested_words = 0

    # The first length already permits an exhaustive counterexample certificate.
    # The bounded search also terminates quickly if no witness is found there.
    for length in range(3, 10):
        words = [
            "".join(bits)
            for bits in product("01", repeat=length)
        ]

        if (
            length < 3
            or len(words) != 2 ** length
            or len(set(words)) != 2 ** length
            or not all(is_binary_word(word, length) for word in words)
        ):
            raise RuntimeError("Failed to verify the exhaustive binary domain.")

        subsequences = {
            word: two_deletion_subsequences(word)
            for word in words
        }
        tested_words += len(words)
        maximum = max(len(values) for values in subsequences.values())

        alternating_words = tuple(
            "".join(str((start + i) % 2) for i in range(length))
            for start in (0, 1)
        )

        for witness in words:
            if is_alternating(witness):
                continue
            if len(subsequences[witness]) != maximum:
                continue

            # Independently verify every count used in the global maximum.
            independent = {
                word: independently_count_subsequences(word)
                for word in words
            }
            hypotheses_verified = (
                isinstance(length, int)
                and length >= 3
                and is_binary_word(witness, length)
                and all(
                    is_binary_word(target, length - 2)
                    and is_subsequence(target, witness)
                    for target in independent[witness]
                )
            )
            counts_verified = all(
                independent[word] == subsequences[word]
                for word in words
            )
            exclusivity_violated = (
                witness not in alternating_words
                and not is_alternating(witness)
                and len(independent[witness])
                == max(len(values) for values in independent.values())
            )

            if hypotheses_verified and counts_verified and exclusivity_violated:
                maximizers = [
                    word for word in words
                    if len(independent[word]) == maximum
                ]
                print("Exact exhaustive counterexample to unique maximization.")
                print("L =", length)
                print("Nonalternating witness y =", repr(witness))
                print(
                    "Distinct length-(L-2) subsequences =",
                    sorted(independent[witness]),
                )
                print("N_2(y) =", len(independent[witness]))
                print("Global maximum over all 2^L binary words =", maximum)
                print("All maximizers =", maximizers)
                print(
                    "Alternating-word counts =",
                    {
                        word: len(independent[word])
                        for word in alternating_words
                    },
                )
                print(
                    "Every hypothesis and every count was verified exactly; "
                    "a nonalternating word attains the global maximum."
                )
                print("VERDICT: COUNTEREXAMPLE_VERIFIED")
                return

    print(
        "Exhaustively checked all binary words for 3 <= L <= 9 "
        f"({tested_words} words), using exact subsequence sets. "
        "No nonalternating maximizer was found."
    )
    print("VERDICT: CONSISTENT_NO_COUNTEREXAMPLE")


if __name__ == "__main__":
    main()
