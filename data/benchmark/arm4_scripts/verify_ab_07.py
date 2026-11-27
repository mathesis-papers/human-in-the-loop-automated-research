#!/usr/bin/env python3
"""
Exact counterexample to strong subadditivity of quantum subentropy.

Take A, B, C to be qubits and set

    rho_ABC = (I_A / 2) tensor |Phi+><Phi+|_BC,
    |Phi+> = (|00> + |11>) / sqrt(2).

All matrix entries, partial traces, and density-matrix checks below use
fractions. Positivity and spectra are certified exactly by verifying that
each matrix is a positive scalar multiple of a Hermitian projector.

For a density matrix with m equal nonzero eigenvalues 1/m, the continuous
extension of the stated subentropy formula gives

    Q = ln(m) - H_m + 1.

Zero eigenvalues do not change subentropy. Thus this formula also applies
to the rank-deficient matrices in this example, including pure states.

The strong-subadditivity defect is exactly

    Q(ABC) + Q(B) - Q(AB) - Q(BC) = 1/12 > 0.

Only the Python standard library is required.
"""

from fractions import Fraction
from decimal import Decimal, localcontext
from math import prod


F = Fraction


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def zeros(n):
    return [[F(0) for _ in range(n)] for _ in range(n)]


def matmul(a, b):
    n = len(a)
    require(len(b) == n, "Matrix dimensions must agree.")
    return [
        [
            sum((a[i][k] * b[k][j] for k in range(n)), F(0))
            for j in range(n)
        ]
        for i in range(n)
    ]


def decode(index, dims):
    coordinates = [0] * len(dims)
    for k in range(len(dims) - 1, -1, -1):
        coordinates[k] = index % dims[k]
        index //= dims[k]
    return tuple(coordinates)


def encode(coordinates, dims):
    index = 0
    for coordinate, dimension in zip(coordinates, dims):
        index = index * dimension + coordinate
    return index


def partial_trace(rho, dims, keep):
    """Trace out every tensor factor whose index is absent from keep."""
    keep = tuple(keep)
    require(len(set(keep)) == len(keep), "Repeated subsystem index.")
    require(all(0 <= k < len(dims) for k in keep), "Invalid subsystem.")
    kept_dims = tuple(dims[k] for k in keep)
    discarded = tuple(k for k in range(len(dims)) if k not in keep)
    result = zeros(prod(kept_dims))
    coordinates = [decode(i, dims) for i in range(prod(dims))]

    for i, ci in enumerate(coordinates):
        for j, cj in enumerate(coordinates):
            if all(ci[k] == cj[k] for k in discarded):
                ii = encode(tuple(ci[k] for k in keep), kept_dims)
                jj = encode(tuple(cj[k] for k in keep), kept_dims)
                result[ii][jj] += rho[i][j]
    return result


def certify_density_and_uniform_spectrum(rho, rank):
    """
    Certify exactly that rho has rank positive eigenvalues equal to 1/rank,
    and all remaining eigenvalues zero.

    If P = rank*rho is Hermitian and P^2 = P, its eigenvalues are 0 or 1.
    Hence rho is positive semidefinite. Its exact trace fixes multiplicities.
    """
    n = len(rho)
    require(n > 0 and all(len(row) == n for row in rho),
            "Density matrix must be square.")
    require(all(isinstance(x, F) for row in rho for x in row),
            "Matrix entries must be exact fractions.")
    require(1 <= rank <= n, "Invalid proposed rank.")
    require(all(rho[i][j] == rho[j][i] for i in range(n) for j in range(n)),
            "Hermiticity failed.")
    require(sum((rho[i][i] for i in range(n)), F(0)) == 1,
            "Trace normalization failed.")

    projector = [[rank * x for x in row] for row in rho]
    require(matmul(projector, projector) == projector,
            "Projector identity failed; positivity/spectrum not certified.")
    require(sum((projector[i][i] for i in range(n)), F(0)) == rank,
            "Projector rank certificate failed.")

    return [F(1, rank)] * rank + [F(0)] * (n - rank)


def harmonic(n):
    return sum((F(1, k) for k in range(1, n + 1)), F(0))


def decimal_fraction(x):
    return Decimal(x.numerator) / Decimal(x.denominator)


def uniform_subentropy(rank):
    # Continuous repeated-eigenvalue limit of the proposition's formula.
    return Decimal(rank).ln() - decimal_fraction(harmonic(rank)) + Decimal(1)


def main():
    dims = (2, 2, 2)
    require(prod(dims) == 8, "Incorrect tensor-product dimension.")

    # Construct rho_A tensor |Phi+><Phi+|_BC directly, using exact entries.
    rho_abc = zeros(8)
    for i in range(8):
        a, b, c = decode(i, dims)
        for j in range(8):
            aa, bb, cc = decode(j, dims)
            if a == aa and b == c and bb == cc:
                rho_abc[i][j] = F(1, 4)

    rho_b = partial_trace(rho_abc, dims, (1,))
    rho_ab = partial_trace(rho_abc, dims, (0, 1))
    rho_bc = partial_trace(rho_abc, dims, (1, 2))

    expected_b = [
        [F(1, 2), F(0)],
        [F(0), F(1, 2)],
    ]
    expected_ab = [
        [F(1, 4) if i == j else F(0) for j in range(4)]
        for i in range(4)
    ]
    expected_bc = [
        [F(1, 2), F(0), F(0), F(1, 2)],
        [F(0), F(0), F(0), F(0)],
        [F(0), F(0), F(0), F(0)],
        [F(1, 2), F(0), F(0), F(1, 2)],
    ]
    require(rho_b == expected_b, "Incorrect B marginal.")
    require(rho_ab == expected_ab, "Incorrect AB marginal.")
    require(rho_bc == expected_bc, "Incorrect BC marginal.")

    matrices = {
        "ABC": (rho_abc, 2),
        "B": (rho_b, 2),
        "AB": (rho_ab, 4),
        "BC": (rho_bc, 1),
    }
    spectra = {
        name: certify_density_and_uniform_spectrum(matrix, rank)
        for name, (matrix, rank) in matrices.items()
    }

    # Every strictly positive spectral value is checked exactly.
    for name, (_, rank) in matrices.items():
        positive = [x for x in spectra[name] if x > 0]
        require(len(positive) == rank, "Wrong number of positive eigenvalues.")
        require(all(x == F(1, rank) for x in positive),
                "Uniform positive spectrum check failed.")
        require(all(x >= 0 for x in spectra[name]), "Negative eigenvalue.")
        require(sum(spectra[name], F(0)) == 1, "Spectrum not normalized.")

    # Repeated and zero eigenvalues are explicitly admitted by the claim's
    # continuous extension and its quantification over every tripartite state.
    #
    # Logarithms cancel exactly because 2*2 = 4*1:
    # ln(2) + ln(2) - ln(4) - ln(1) = 0.
    require(2 * 2 == 4 * 1, "Logarithmic cancellation failed.")
    exact_defect = (
        -harmonic(2) - harmonic(2) + harmonic(4) + harmonic(1)
    )
    require(exact_defect == F(1, 12), "Unexpected exact SSA defect.")
    require(exact_defect > 0, "No strict violation.")

    with localcontext() as ctx:
        ctx.prec = 70
        q = {name: uniform_subentropy(rank)
             for name, (_, rank) in matrices.items()}
        lhs = q["ABC"] + q["B"]
        rhs = q["AB"] + q["BC"]
        require(abs((lhs - rhs) - decimal_fraction(exact_defect))
                < Decimal("1e-60"),
                "High-precision evaluation disagrees with exact certificate.")
        require(lhs - rhs > Decimal("0.000001"),
                "Violation does not exceed 1e-6.")

        print("Witness: rho_ABC = (I_2/2)_A tensor |Phi+><Phi+|_BC.")
        print("Subsystem dimensions: A = B = C = 2.")
        print("Basis order: |000>, |001>, ..., |111>.")
        print("Exact rho_ABC:")
        for row in rho_abc:
            print("  [" + ", ".join(map(str, row)) + "]")
        print("Verified exactly: Hermiticity, trace 1, positive semidefiniteness,")
        print("tensor dimensions, all required partial traces, and all spectra.")
        for name in ("ABC", "B", "AB", "BC"):
            print(f"Spectrum({name}) = "
                  f"[{', '.join(map(str, spectra[name]))}]")
            print(f"Q({name}) = {q[name]:.30f}")
        print(f"SSA left side  = {lhs:.30f}")
        print(f"SSA right side = {rhs:.30f}")
        print("Exact left-minus-right defect = 1/12 > 0.")
        print("VERDICT: COUNTEREXAMPLE_VERIFIED")


if __name__ == "__main__":
    main()
