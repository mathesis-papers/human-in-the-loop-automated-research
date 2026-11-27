#!/usr/bin/env python3
"""Exact counterexample to the stated one-mode Wigner normalization claim."""

import sympy as sp


def require(condition, description):
    if condition is not True:
        raise AssertionError("Verification failed: " + description)


def main():
    # Choose an explicit admissible instance. All calculations below are exact.
    sigma = sp.Integer(1)
    hbar = sp.Integer(1)
    x, xp, q, p, y = sp.symbols("x xp q p y", real=True)

    require(sigma.is_positive is True, "sigma > 0")
    require(hbar == 1, "hbar = 1")

    def psi(t):
        return (sp.pi * sigma**2) ** (-sp.Rational(1, 4)) * sp.exp(
            -t**2 / (2 * sigma**2)
        )

    def rho(a, b):
        return psi(a) * sp.conjugate(psi(b))

    # Verify the wave function is exactly the prescribed Gaussian.
    prescribed_psi = sp.pi ** (-sp.Rational(1, 4)) * sp.exp(-x**2 / 2)
    require(sp.simplify(psi(x) - prescribed_psi) == 0,
            "prescribed Gaussian wave function")

    # A normalized rank-one kernel |psi><psi| is a positive, pure density
    # operator. Check normalization, Hermiticity, trace and idempotence exactly.
    norm = sp.integrate(
        sp.simplify(psi(x) * sp.conjugate(psi(x))),
        (x, -sp.oo, sp.oo),
    )
    require(norm == 1, "wave-function normalization")

    require(sp.simplify(rho(x, xp) - sp.conjugate(rho(xp, x))) == 0,
            "Hermiticity")
    trace = sp.integrate(rho(x, x), (x, -sp.oo, sp.oo))
    require(trace == 1, "density-operator trace")

    # Positivity follows exactly from the displayed factorization:
    # <f|rho|f> = |<psi|f>|^2 >= 0 for every f.
    require(sp.simplify(rho(x, xp) -
                        psi(x) * sp.conjugate(psi(xp))) == 0,
            "positive rank-one factorization")
    rho_squared = psi(x) * norm * sp.conjugate(psi(xp))
    require(sp.simplify(rho_squared - rho(x, xp)) == 0,
            "purity: rho squared equals rho")

    shifted_kernel = sp.simplify(rho(q + y, q - y))
    expected_kernel = sp.exp(-q**2 - y**2) / sp.sqrt(sp.pi)
    require(sp.simplify(shifted_kernel - expected_kernel) == 0,
            "density kernel at the arguments in the definition")

    # Evaluate the defining Fourier integral exactly. Its imaginary part
    # vanishes because the sine integrand is odd and absolutely integrable.
    sine_integrand = sp.exp(-y**2) * sp.sin(2 * p * y)
    require(sp.simplify(sine_integrand.subs(y, -y) + sine_integrand) == 0,
            "oddness of the imaginary integrand")
    gaussian_mass = sp.integrate(sp.exp(-y**2), (y, -sp.oo, sp.oo))
    require(gaussian_mass == sp.sqrt(sp.pi),
            "integrable Gaussian bound for the Fourier integral")

    cosine_transform = sp.integrate(
        sp.exp(-y**2) * sp.cos(2 * p * y),
        (y, -sp.oo, sp.oo),
    )
    require(sp.simplify(cosine_transform -
                        sp.sqrt(sp.pi) * sp.exp(-p**2)) == 0,
            "exact Gaussian Fourier transform")

    wigner = sp.simplify(
        sp.exp(-q**2) * cosine_transform /
        (2 * sp.pi * sp.sqrt(sp.pi))
    )
    expected_wigner = sp.exp(-q**2 - p**2) / (2 * sp.pi)
    require(sp.simplify(wigner - expected_wigner) == 0,
            "W is computed with the proposition's exact prefactor")

    # W is a nonnegative, separable Gaussian, so these exact Gaussian
    # integrals also establish absolute integrability of the double integral.
    q_mass = sp.integrate(sp.exp(-q**2), (q, -sp.oo, sp.oo))
    p_mass = sp.integrate(sp.exp(-p**2), (p, -sp.oo, sp.oo))
    total_mass = sp.simplify(q_mass * p_mass / (2 * sp.pi))
    require(total_mass == sp.Rational(1, 2),
            "exact double integral of W")
    require(abs(total_mass - 1) > sp.Rational(1, 10**6),
            "strict violation of the claimed normalization")

    print("Explicit witness: hbar = 1, sigma = 1.")
    print("psi(x) = pi^(-1/4) exp(-x^2/2).")
    print("rho(x,x') = pi^(-1/2) exp(-(x^2+x'^2)/2).")
    print("Verified exactly: sigma > 0; prescribed Gaussian; norm = 1;")
    print("Hermitian, positive rank-one density operator; trace = 1; purity.")
    print("The stated definition gives W(q,p) = exp(-q^2-p^2)/(2*pi).")
    print("Exact double integral of W =", total_mass)
    print("Exact discrepancy from the claimed value 1 =", total_mass - 1)
    print("Proof error: delta(2*y) = delta(y)/2.")
    print("VERDICT: COUNTEREXAMPLE_VERIFIED")


if __name__ == "__main__":
    main()
