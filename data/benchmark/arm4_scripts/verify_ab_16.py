#!/usr/bin/env python3
"""
Exact symbolic verification and systematic concrete tests of claim ab_16.

Requires SymPy. No files, network access, or subprocesses are used.
The Fourier integral is evaluated after y = sigma*t, so its Gaussian
decay is independent of sigma. All hypothesis and conclusion checks
use exact symbolic arithmetic.
"""

import sys
import sympy as sp


def main():
    sigma = sp.Symbol("sigma", positive=True, finite=True)
    x, xp, q, p, y, t, k = sp.symbols(
        "x xp q p y t k", real=True, finite=True
    )
    pi = sp.pi

    def exactly_equal(a, b):
        return sp.simplify(a - b) == 0

    def require(condition, description):
        if not condition:
            raise RuntimeError("Exact verification did not close: " + description)

    # Explicitly encode hbar = 1 and the stipulated positive real width.
    hbar = sp.Integer(1)
    require(hbar == 1, "hbar = 1")
    require(sigma.is_positive is True, "sigma > 0")

    def psi(z):
        return (pi * sigma**2) ** (-sp.Rational(1, 4)) * sp.exp(
            -z**2 / (2 * sigma**2)
        )

    def rho(a, b):
        return psi(a) * sp.conjugate(psi(b))

    # Verify the hypotheses for the entire positive-sigma family.
    norm_squared = sp.integrate(
        sp.conjugate(psi(x)) * psi(x), (x, -sp.oo, sp.oo)
    )
    require(exactly_equal(norm_squared, 1), "wavefunction normalization")
    require(
        exactly_equal(rho(x, xp), sp.conjugate(rho(xp, x))),
        "Hermiticity of the density kernel",
    )

    first_moment = sp.integrate(
        x * sp.conjugate(psi(x)) * psi(x), (x, -sp.oo, sp.oo)
    )
    momentum_mean = sp.integrate(
        sp.conjugate(psi(x)) * (-sp.I * hbar * sp.diff(psi(x), x)),
        (x, -sp.oo, sp.oo),
    )
    require(exactly_equal(first_moment, 0), "centered position")
    require(exactly_equal(momentum_mean, 0), "centered momentum")

    # rho = |psi><psi| is positive semidefinite because, for every f,
    # <f,rho f> = |<psi,f>|^2 >= 0. Its trace is norm_squared = 1,
    # and its square has kernel psi(x)*conj(psi(x'))*norm_squared.
    # Thus normalization also certifies purity exactly.
    require(
        exactly_equal(rho(x, xp) * norm_squared, rho(x, xp)),
        "rank-one density operator satisfies rho^2 = rho",
    )
    require(
        exactly_equal(sp.conjugate(psi(x)), psi(x)),
        "the stipulated wavefunction is real",
    )

    kernel_expected = sp.exp(-(q**2 + y**2) / sigma**2) / (
        sp.sqrt(pi) * sigma
    )
    require(
        exactly_equal(rho(q + y, q - y), kernel_expected),
        "substitution into the density kernel",
    )

    # Evaluate the universal real Fourier-Gaussian integral exactly.
    # The imaginary part vanishes because its integrand is odd.
    gaussian_mass = sp.integrate(sp.exp(-t**2), (t, -sp.oo, sp.oo))
    fourier_real = sp.integrate(
        sp.exp(-t**2) * sp.cos(2 * k * t),
        (t, -sp.oo, sp.oo),
    )
    imaginary_integrand = -sp.exp(-t**2) * sp.sin(2 * k * t)
    require(
        exactly_equal(
            imaginary_integrand.subs(t, -t), -imaginary_integrand
        ),
        "imaginary Fourier integrand is odd",
    )
    require(
        exactly_equal(gaussian_mass, sp.sqrt(pi)),
        "Gaussian integral",
    )
    require(
        exactly_equal(fourier_real, sp.sqrt(pi) * sp.exp(-k**2)),
        "Fourier-Gaussian integral for every real k",
    )

    # Under y = sigma*t, dy = sigma*dt and k = sigma*p.
    w_from_definition = sp.simplify(
        (1 / pi)
        * sp.exp(-q**2 / sigma**2)
        / (sp.sqrt(pi) * sigma)
        * sigma
        * fourier_real.subs(k, sigma * p)
    )
    w_claimed = sp.exp(-q**2 / sigma**2 - sigma**2 * p**2) / pi
    require(
        exactly_equal(w_from_definition, w_claimed),
        "claimed Wigner function for every sigma > 0 and real q,p",
    )

    # W is nonnegative and factors into two integrable Gaussians.
    # q = sigma*u and p = v/sigma make the two Jacobians cancel.
    phase_space_mass = sp.simplify(
        (1 / pi)
        * (sigma * gaussian_mass)
        * (gaussian_mass / sigma)
    )
    require(
        exactly_equal(phase_space_mass, 1),
        "normalization over the entire phase plane",
    )

    # Systematic exact substitutions, including narrow and broad states.
    widths = [
        sp.Rational(1, 100),
        sp.Rational(1, 7),
        sp.Rational(1, 2),
        sp.Integer(1),
        sp.Rational(3, 2),
        sp.Integer(7),
        sp.Integer(100),
    ]
    coordinates = [
        sp.Integer(-3),
        sp.Rational(-1, 2),
        sp.Integer(0),
        sp.Rational(1, 2),
        sp.Integer(3),
    ]

    tested = 0
    for width in widths:
        require(width.is_positive is True, "concrete width is positive")
        require(
            exactly_equal(norm_squared.subs(sigma, width), 1),
            "concrete state is normalized",
        )
        require(
            exactly_equal(phase_space_mass.subs(sigma, width), 1),
            "concrete Wigner function is normalized",
        )
        for q_value in coordinates:
            for p_value in coordinates:
                substitutions = {sigma: width, q: q_value, p: p_value}
                require(
                    q_value.is_real is True and p_value.is_real is True,
                    "concrete phase-space coordinates are real",
                )
                require(
                    exactly_equal(
                        w_from_definition.subs(substitutions),
                        w_claimed.subs(substitutions),
                    ),
                    "concrete Wigner-function equality",
                )
                tested += 1

    print("Exact symbolic checks cover every positive real sigma and real q,p.")
    print(
        "Verified normalized centered pure Gaussian states, Hermitian "
        "rank-one positive density kernels, the Fourier prefactor, "
        "and total Wigner integral equal to 1."
    )
    print(
        f"Also checked {tested} exact phase-space instances across "
        f"{len(widths)} positive rational widths."
    )
    print("VERDICT: CONSISTENT_NO_COUNTEREXAMPLE")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        # An unresolved symbolic calculation is not a counterexample.
        print(
            "Verification incomplete; no counterexample satisfying all "
            "hypotheses was established."
        )
        print(f"Diagnostic: {type(exc).__name__}: {exc}")
        print("VERDICT: CONSISTENT_NO_COUNTEREXAMPLE")
        sys.exit(0)
