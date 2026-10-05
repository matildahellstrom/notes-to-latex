"""Independent check of the final answers in the transcribed notes (komplex-2018).

Each check: (page, description, value computed independently, value claimed in the notes).
Contour integrals are integrated numerically along the parametrised contour; real integrals
with mpmath.quad; residues, series and ODEs with sympy.
"""
import mpmath as mp
import sympy as sp

mp.mp.dps = 30
z, t, x, s, w = sp.symbols("z t x s w")
I, pi, E = sp.I, sp.pi, sp.E


def circle(f, c, r, n=1):
    """∮ f dz over |z - c| = r, n times counter-clockwise."""
    g = lambda th: f(c + r * mp.e**(1j * th)) * 1j * r * mp.e**(1j * th)
    return n * mp.quad(g, [0, mp.pi / 2, mp.pi, 3 * mp.pi / 2, 2 * mp.pi])


def square(f, a):  # boundary of the square with corners ±a±ai, counter-clockwise
    pts = [a - a * 1j, a + a * 1j, -a + a * 1j, -a - a * 1j, a - a * 1j]
    tot = 0
    for p, q in zip(pts, pts[1:]):
        tot += mp.quad(lambda u: f(p + (q - p) * u) * (q - p), [0, 1])
    return tot


def zeros_in(poly_coeffs, cond):
    return sum(1 for r in mp.polyroots(poly_coeffs, maxsteps=200, extraprec=60) if cond(r))


def num(e):
    return complex(sp.N(e, 25))


checks = []
add = lambda page, what, got, claim: checks.append((page, what, complex(got), num(claim) if isinstance(claim, sp.Basic) else complex(claim)))

# --- komplexa tal, Möbius ---------------------------------------------------------------
add(11, "((-1+i√3)/2)^3", ((-1 + 1j * mp.sqrt(3)) / 2) ** 3, 1)
r1 = -1 + (1 + 1j) / mp.sqrt(2)
add(11, "z²+2z+(1-i)=0 has root -1+(1+i)/√2", r1**2 + 2 * r1 + (1 - 1j), 0)
add(2, "|2-2i|", abs(2 - 2j), 2 * sp.sqrt(2))
add(2, "Arg(2-2i)", mp.arg(2 - 2j), -pi / 4)
add(25, "i^i (principal)", mp.power(1j, 1j), sp.exp(-pi / 2))
add(24, "f(-1-i), f=2z/(z+2)", 2 * (-1 - 1j) / ((-1 - 1j) + 2), -2 * I)
M = lambda z_: (z_ - 1) / (1j * z_ - 1)
add(17, "M(i), M=(z-1)/(iz-1)", M(1j), (1 - I) / 2)
add(28, "M(1), M=(z+i)/(iz+1)", (1 + 1j) / (1j + 1), 1)
add(28, "f(C(1,1)) = C(1/2,1/2): |f(1+i) - 1/2|", abs(2 * (1 + 1j) / (3 + 1j) - 0.5), sp.Rational(1, 2))
add(29, "M(1) for M=z/(z+i)", 1 / (1 + 1j), (1 - I) / 2)

# --- kurvintegraler ---------------------------------------------------------------------
add(20, "∫ z̄ dz along t+it", mp.quad(lambda u: (u - 1j * u) * (1 + 1j), [0, 1]), 1)
add(20, "∫ z̄ dz along t+it²", mp.quad(lambda u: (u - 1j * u**2) * (1 + 2j * u), [0, 1]), 1 + I / 3)
add(26, "∮_{C[0,2]} (z+z̄) dz", circle(lambda q: q + mp.conj(q), 0, 2), 8 * pi * I)
add(26, "∮_{C[0,2]} dz/(z²+1)", circle(lambda q: 1 / (q**2 + 1), 0, 2), 0)
add(27, "∮_{C[-1,2]} z²/(4-z²)", circle(lambda q: q**2 / (4 - q**2), -1, 2), 2 * pi * I)
add(27, "∮_{C[0,1]} sin z/z", circle(lambda q: mp.sin(q) / q, 0, 1), 0)
add(27, "∮_{C[0,2]} e^z/(z(z-3))", circle(lambda q: mp.e**q / (q * (q - 3)), 0, 2), -2 * pi * I / 3)
add(30, "∮_{|z-2|=1} e^z/z²", circle(lambda q: mp.e**q / q**2, 2, 1), 0)
add(30, "∮_{|z|=1} dz/(z²+2z)", circle(lambda q: 1 / (q**2 + 2 * q), 0, 1), pi * I)
add(32, "∮_{|z|=1} e^z/z", circle(lambda q: mp.e**q / q, 0, 1), 2 * pi * I)
add(32, "∮_γ sin z/(1-z), γ ~ -2·C(1,r)", circle(lambda q: mp.sin(q) / (1 - q), 1, 0.5, n=-2), 4 * pi * I * sp.sin(1))
add(33, "∮_{|z|=1} sin z/z²", circle(lambda q: mp.sin(q) / q**2, 0, 1), 2 * pi * I)
for k in (1, 2, 4):
    add(33, f"∮_{{|z|=1}} e^z/z^{k}", circle(lambda q: mp.e**q / q**k, 0, 1), 2 * pi * I / sp.factorial(k - 1))
add(37, "∫ e^z along it, t∈[0,π]", mp.quad(lambda u: mp.e**(1j * u) * 1j, [0, mp.pi]), -2)
add(41, "∫_□ e^z cos z/(z-π)³ (±4±4i)", square(lambda q: mp.e**q * mp.cos(q) / (q - mp.pi)**3, 4), 0)
add(41, "∮_{|z|=3} e^{2z}/((z-1)²(z-2))", circle(lambda q: mp.e**(2 * q) / ((q - 1)**2 * (q - 2)), 0, 3), 2 * pi * I * E**2 * (E**2 - 3))
add(68, "∮_{C[0,3]} cot z", circle(lambda q: mp.cot(q), 0, 3), 2 * pi * I)
add(68, "∮_{C[0,3]} dz/((z+4)(z²+1))", circle(lambda q: 1 / ((q + 4) * (q**2 + 1)), 0, 3), -2 * pi * I / 17)
add(69, "∮_{C[0,3]} z² e^{1/z}", circle(lambda q: q**2 * mp.e**(1 / q), 0, 3), pi * I / 3)
add(69, "∮_{C[0,1]} dz/(z² sin z)", circle(lambda q: 1 / (q**2 * mp.sin(q)), 0, 1), pi * I / 3)
add(72, "∮_{|z-2|=1} dz/((z²-4)(z-2))", circle(lambda q: 1 / ((q**2 - 4) * (q - 2)), 2, 1), -pi * I / 8)
add(72, "∮_{|z+2|=2} e^z/(z+1)^34", circle(lambda q: mp.e**q / (q + 1)**34, -2, 2), 2 * pi * I * sp.exp(-1) / sp.factorial(33))
add(73, "∮_{|z|=2} e^z/(z³+z)", circle(lambda q: mp.e**q / (q**3 + q), 0, 2), 2 * pi * I * (1 - sp.cos(1)))
add(74, "∮_{|z-1|=3} e^z/(sin z (z-1)²)", circle(lambda q: mp.e**q / (mp.sin(q) * (q - 1)**2), 1, 3),
    2 * pi * I * (E * (sp.sin(1) - sp.cos(1)) / sp.sin(1)**2 - sp.exp(pi) / (pi - 1)**2 + 1))
add(75, "∮_{|z|=1} e^z sin(1/z)", circle(lambda q: mp.e**q * mp.sin(1 / q), 0, 1),
    2 * pi * I * sp.Sum((-1)**sp.Symbol('k') / (sp.factorial(2 * sp.Symbol('k')) * sp.factorial(2 * sp.Symbol('k') + 1)), (sp.Symbol('k'), 0, 30)).doit())
add(99, "∮_{|z|=1} (e^z - e^{-z})/z", circle(lambda q: (mp.e**q - mp.e**(-q)) / q, 0, 1), 0)
add(99, "∮_{|z|=1} (sin z - sinh z)/z⁸", circle(lambda q: (mp.sin(q) - mp.sinh(q)) / q**8, 0, 1), -4 * pi * I / sp.factorial(7))

# --- residyer ---------------------------------------------------------------------------
res = lambda f, p: sp.residue(f, z, p)
add(65, "Res_1 e^z/(sin z (z-1)²)", num(res(sp.exp(z) / (sp.sin(z) * (z - 1)**2), 1)), E * (sp.sin(1) - sp.cos(1)) / sp.sin(1)**2)
add(66, "Res_π e^z/(sin z (z-1)²)", num(res(sp.exp(z) / (sp.sin(z) * (z - 1)**2), pi)), -sp.exp(pi) / (pi - 1)**2)
add(69, "Res_0 e^{1-1/z}", mp.quad(lambda th: mp.e**(1 - mp.e**(-1j * th)) * mp.e**(1j * th), [0, 2 * mp.pi]) / (2 * mp.pi), -E)
add(73, "Res_0 (e^{4z}-1)/sin²z", num(res((sp.exp(4 * z) - 1) / sp.sin(z)**2, 0)), 4)
add(72, "Res_2 1/((z²-4)(z-2))", num(res(1 / ((z**2 - 4) * (z - 2)), 2)), sp.Rational(-1, 16))
add(75, "Res_{-2+√3} -i(z²+1)/(z³+4z²+z)", num(res(-I * (z**2 + 1) / (z**3 + 4 * z**2 + z), -2 + sp.sqrt(3))), 2 * I / sp.sqrt(3))
add(76, "Res_{e^{iπ/3}} 1/(1+z³)", num(res(1 / (1 + z**3), sp.exp(I * pi / 3))), 1 / (3 * sp.exp(2 * pi * I / 3)))
add(105, "Res_{√(3-2√2)} 4iz/(z⁴-6z²+1)", num(res(4 * I * z / (z**4 - 6 * z**2 + 1), sp.sqrt(3 - 2 * sp.sqrt(2)))), -I / (2 * sp.sqrt(2)))
add(107, "Res_i e^{-itz}/((z²+1)(z²+4)) at t=-1", num(res(sp.exp(I * z) / ((z**2 + 1) * (z**2 + 4)), I)), -I * sp.exp(-1) / 6)
add(107, "Res_2i e^{-itz}/((z²+1)(z²+4)) at t=-1", num(res(sp.exp(I * z) / ((z**2 + 1) * (z**2 + 4)), 2 * I)), I * sp.exp(-2) / 12)

# --- reella integraler --------------------------------------------------------------------
inf = mp.inf
add(35, "∫ dx/(1+x²)", mp.quad(lambda u: 1 / (1 + u**2), [-inf, inf]), pi)
add(36, "∫ cos 2x/(1+x²)", mp.quadosc(lambda u: mp.cos(2 * u) / (1 + u**2), [-inf, inf], omega=2), pi * sp.exp(-2))
add(41, "∫_0^{2π} dt/(2+sin t)", mp.quad(lambda u: 1 / (2 + mp.sin(u)), [0, 2 * mp.pi]), 2 * pi / sp.sqrt(3))
add(42, "∫ cos x/(1+x⁴)", mp.quadosc(lambda u: mp.cos(u) / (1 + u**4), [-inf, inf], omega=1),
    pi * sp.exp(-1 / sp.sqrt(2)) * sp.sin(3 * pi / 4 - 1 / sp.sqrt(2)))
add(70, "∫ dx/(1+x²)²", mp.quad(lambda u: 1 / (1 + u**2)**2, [-inf, inf]), pi / 2)
add(75, "∫_0^{2π} cos t/(cos t+2)", mp.quad(lambda u: mp.cos(u) / (mp.cos(u) + 2), [0, 2 * mp.pi]), 2 * pi * (1 - 2 / sp.sqrt(3)))
add(76, "∫_0^∞ dx/(1+x³)", mp.quad(lambda u: 1 / (1 + u**3), [0, inf]), 2 * pi / (3 * sp.sqrt(3)))
for k in (0, 1, 3):
    add(84, f"∫_0^{{2π}} cos^{2*k} t", mp.quad(lambda u: mp.cos(u)**(2 * k), [0, 2 * mp.pi]), pi * sp.binomial(2 * k, k) / 2**(2 * k - 1))
for a in (0.5, -2):
    add(84, f"∫ cos({a}x)/(1+x²)", mp.quadosc(lambda u: mp.cos(a * u) / (1 + u**2), [-inf, inf], omega=abs(a)), pi * sp.exp(-abs(sp.nsimplify(a))))
for a, b in ((1, 2), (3, 1.5)):
    add(96, f"∫ sin({a}x)sin({b}x)/x²", mp.quadosc(lambda u: mp.sin(a * u) * mp.sin(b * u) / u**2, [-inf, inf], omega=min(a, b)), pi * min(a, b))
for a, b in ((2, 1), (5, 3)):
    add(93, f"∫_0^{{2π}} dt/({a}+{b} sin t)", mp.quad(lambda u: 1 / (a + b * mp.sin(u)), [0, 2 * mp.pi]), 2 * pi / sp.sqrt(a**2 - b**2))
add(94, "∫ dx/(1+x⁴)", mp.quad(lambda u: 1 / (1 + u**4), [-inf, inf]), pi / sp.sqrt(2))
add(105, "∫_0^π dt/(1+sin²t)", mp.quad(lambda u: 1 / (1 + mp.sin(u)**2), [0, mp.pi]), pi / sp.sqrt(2))

# --- Fourier ------------------------------------------------------------------------------
FT = lambda f, xx: mp.quadosc(lambda u: f(u) * mp.cos(xx * u), [-inf, inf], omega=max(abs(xx), 0.5)) if xx else mp.quad(f, [-inf, inf])
for xx in (0, 0.7, 2):
    X = sp.nsimplify(xx)
    add(81, f"FT e^-|t| at x={xx}", FT(lambda u: mp.e**(-abs(u)), xx), 2 / (1 + X**2))
    add(82, f"FT 1/(1+t²) at x={xx}", FT(lambda u: 1 / (1 + u**2), xx), pi * sp.exp(-abs(X)))
    add(83, f"FT e^-t²/2 at x={xx}", FT(lambda u: mp.e**(-u**2 / 2), xx), sp.sqrt(2 * pi) * sp.exp(-X**2 / 2))
    add(86, f"FT f_δ (δ=6) at x={xx}", mp.quad(lambda u: mp.e**(-1j * xx * u), [-6, 6]), 12 if xx == 0 else 2 * sp.sin(6 * X) / X)
    add(107, f"FT 1/((x²+1)(x²+4)) at t={xx}", FT(lambda u: 1 / ((u**2 + 1) * (u**2 + 4)), xx),
        pi * sp.exp(-abs(X)) / 6 * (2 - sp.exp(-abs(X))))
    add(95, f"∫ 1/(1+s²)·1/(1+(s-t)²) at t={xx}", mp.quad(lambda u: 1 / (1 + u**2) / (1 + (u - xx)**2), [-inf, inf]), 2 * pi / (4 + X**2))
for xx in (0.7, -1.3):
    X = sp.nsimplify(xx)
    got = mp.quad(lambda u: mp.e**(-1j * xx * u) / (u**2 + 4 * u + 5), [-inf, inf])
    add(83, f"FT 1/(t²+4t+5) at x={xx}", got, pi * sp.exp(2 * I * X - abs(X)))

# --- Laplace, Z, differentialekvationer ---------------------------------------------------------
LT = lambda f: sp.laplace_transform(f, t, s, noconds=True)
a_, c_ = sp.Rational(3, 2), 2
for tt in (sp.Rational(1, 3), 2):
    pass
add(97, "LT t²e^{at} at a=3/2, s=4", num(LT(t**2 * sp.exp(a_ * t)).subs(s, 4)), num((2 / (s - a_)**3).subs(s, 4)))
add(89, "LT sin 2t at s=3", num(LT(sp.sin(c_ * t)).subs(s, 3)), sp.Rational(2, 13))
add(89, "LT cos 2t at s=3", num(LT(sp.cos(c_ * t)).subs(s, 3)), sp.Rational(3, 13))
u = sp.Function("u")
def ode(eq, ics, claim, page, label):
    sol = sp.dsolve(eq, u(t), ics=ics).rhs
    for tt in (sp.Rational(1, 2), 2):
        add(page, f"{label} at t={tt}", num(sol.subs(t, tt)), claim.subs(t, tt))
ode(sp.Eq(u(t).diff(t, 2) + u(t), 0), {u(0): 1, u(t).diff(t).subs(t, 0): 2}, sp.cos(t) + 2 * sp.sin(t), 89, "u''+u=0")
ode(sp.Eq(u(t).diff(t, 2) + u(t), 1), {u(0): 1, u(t).diff(t).subs(t, 0): 2}, 2 * sp.sin(t) + 1, 90, "u''+u=1")
ode(sp.Eq(u(t).diff(t, 2) - 2 * u(t).diff(t) + 2 * u(t), 6 * sp.exp(t)), {u(0): 0, u(t).diff(t).subs(t, 0): 1},
    sp.exp(t) * (6 - 6 * sp.cos(t) + sp.sin(t)), 97, "u''-2u'+2u=6e^t")
ode(sp.Eq(u(t).diff(t, 2) - 2 * u(t).diff(t) + 5 * u(t), sp.exp(-t)), {u(0): 1, u(t).diff(t).subs(t, 0): 2},
    sp.exp(-t) / 8 + sp.Rational(7, 8) * sp.exp(t) * sp.cos(2 * t) + sp.Rational(5, 8) * sp.exp(t) * sp.sin(2 * t), 109, "y''-2y'+5y=e^-t")
# u''+u = g, g = 1 for t > π: u = 1 - cos(t - π) for t > π
add(95, "u''+u=H(t-π), u(4)", mp.quad(lambda r: mp.sin(4 - r), [mp.pi, 4]), 1 - sp.cos(4 - pi))
Zt = lambda seq, zz: mp.nsum(lambda k: seq(k) / zz**k, [0, inf])
add(91, "Z{2^k} at z=5", Zt(lambda k: 2**k, 5), sp.Rational(5, 3))
add(97, "Z{k} at z=3", Zt(lambda k: k, 3), sp.Rational(3, 4))
add(98, "Z{k(k-1)} at z=3", Zt(lambda k: k * (k - 1), 3), sp.Rational(6, 8))
a_k = [0]
for k in range(10):
    a_k.append(a_k[-1] + k)
add(98, "a_{k+1}-a_k=k, a_0=0 ⇒ a_9 = C(9,2)", a_k[9], sp.binomial(9, 2))

# --- serier -------------------------------------------------------------------------------
ser = lambda f, p, n: sp.series(f, z, p, n).removeO()
add(56, "sec z: coeff z⁴", num(ser(sp.sec(z), 0, 6).coeff(z, 4)), sp.Rational(5, 24))
add(59, "1/sin z: coeff z³", num(ser(1 / sp.sin(z), 0, 5).coeff(z, 3)), sp.Rational(7, 360))
add(71, "1/sin²z: coeff z²", num(ser(1 / sp.sin(z)**2, 0, 4).coeff(z, 2)), sp.Rational(1, 15))
add(71, "1/sin²z: coeff z⁰", num(ser(1 / sp.sin(z)**2, 0, 4).coeff(z, 0)), sp.Rational(1, 3))
add(53, "sin²z: coeff z⁶", num(ser(sp.sin(z)**2, 0, 8).coeff(z, 6)), (-1)**4 * 2**5 / sp.factorial(6))
add(67, "1/(1+z²) at 1: coeff (z-1)²", num(sp.series(1 / (1 + z**2), z, 1, 3).removeO().subs(z, w + 1).expand().coeff(w, 2)), sp.Rational(1, 4))
add(67, "e^{z²} at i: coeff (z-i)²", num(sp.series(sp.exp((w + I)**2), w, 0, 3).removeO().coeff(w, 2)), -sp.exp(-1))
add(67, "Σ z^k/(k+1) at z=1/2", mp.nsum(lambda k: 0.5**k / (k + 1), [0, inf]), -sp.log(1 - sp.Rational(1, 2)) / sp.Rational(1, 2))
add(56, "sin z - tan z: order of zero (f'''(0))", num(sp.diff(sp.sin(z) - sp.tan(z), z, 3).subs(z, 0)), -3)
add(103, "1/((z-1)(z-2)²) Laurent in 1<|z|<2: c_3", num(sp.Rational(1, 2**4) + sp.Rational(4, 2**5)), sp.Rational(6, 2**5))
add(55, "1/((z-1)(z+1)) at 1: coeff (z-1)^-1", num(sp.residue(1 / ((z - 1) * (z + 1)), z, 1)), sp.Rational(1, 2))
add(71, "1/(z(z-2)²) at 2, 0<|z-2|<2: coeff (z-2)^0", num(sp.series(1 / ((w + 2) * w**2), w, 0, 2).removeO().coeff(w, 0)), sp.Rational(1, 8))
add(60, "1/z² at -1, |z+1|>1: coeff (z+1)^-3", num(sp.series((1 / (w - 1)**2).subs(w, 1 / x), x, 0, 5).removeO().coeff(x, 3)), 2)

# --- nollställen (argumentprincipen / Rouché) ----------------------------------------------
add(79, "#zeros z⁵+2z+1 in Re z>0", zeros_in([1, 0, 0, 0, 2, 1], lambda r: r.real > 0), 2)
add(85, "#zeros z²+z+1 in Re z<0", zeros_in([1, 1, 1], lambda r: r.real < 0), 2)
add(94, "#zeros z³+z²+z+4 in Re z>0", zeros_in([1, 1, 1, 4], lambda r: r.real > 0), 2)
add(106, "#zeros z⁵-5z+3 in Re z>0", zeros_in([1, 0, 0, 0, -5, 3], lambda r: r.real > 0), 2)
add(107, "#zeros z⁴+2z+10 in 1<|z|<2", zeros_in([1, 0, 0, 2, 10], lambda r: 1 < abs(r) < 2), 4)
add(70, "#zeros z⁴-5z+1 in 1≤|z|≤2", zeros_in([1, 0, 0, -5, 1], lambda r: 1 <= abs(r) <= 2), 3)
argcount = lambda f, df, c, r: circle(lambda q: df(q) / f(q), c, r) / (2j * mp.pi)
add(70, "#zeros e^z/3 - z in D(0,1)", argcount(lambda q: mp.e**q / 3 - q, lambda q: mp.e**q / 3 - 1, 0, 1), 1)
add(86, "#zeros 3e^z - z in D(0,1)", argcount(lambda q: 3 * mp.e**q - q, lambda q: 3 * mp.e**q - 1, 0, 1), 0)
add(80, "#zeros 3z³+e^{iz}-1 in D(0,2)", argcount(lambda q: 3 * q**3 + mp.e**(1j * q) - 1, lambda q: 9 * q**2 + 1j * mp.e**(1j * q), 0, 2), 3)

# --- harmonisk ------------------------------------------------------------------------------
X, Y = sp.symbols("X Y", real=True)
uh = X / (X**2 + Y**2)
add(39, "Δ(x/(x²+y²))", num(sp.simplify(sp.diff(uh, X, 2) + sp.diff(uh, Y, 2))), 0)

bad = 0
for page, what, got, claim in checks:
    ok = abs(got - claim) <= 1e-8 * max(1, abs(claim))
    bad += not ok
    if not ok:
        print(f"MISMATCH s.{page}: {what}: computed {got:.10g}, notes say {claim:.10g}")
print(f"{len(checks)} checks, {len(checks) - bad} agree, {bad} differ")
