# Numerical correctness

Define the mathematical problem, valid input domain, units/scales, boundary/initial conditions and expected output before changing a kernel. Separate model error, discretization error, solver stopping error and floating-point error. A tiny residual need not imply a small solution error for an ill-conditioned problem. Conservation checks alone may admit incorrect solutions; combine complementary evidence.

Choose comparisons from the scientific error budget. For finite scalar values, a possible contract is `abs(actual - reference) <= atol + rtol * abs(reference)`; define which value sets the scale, tensor norm/component policy and units. This is an example, not a universal comparator. Near-zero outputs need a justified absolute scale; relative error alone is insufficient. Do not use machine epsilon as a universal scientific tolerance. ULP bounds also need a justified domain and reference.

Handle NaN, infinities and signed zero explicitly before tolerance arithmetic. NaN can make ordered comparisons false and allow an inverted rejection predicate to pass invalid results. Nonfinite equality is acceptable only if the specified operation expects it. Never discard nonfinite samples, clamp invalid results or loosen thresholds simply to pass tests. Check input/output shapes and lengths before zipped comparisons so tails cannot disappear.

Cover representative interior, near-zero, large/small magnitude, degenerate, invalid and boundary cases. Include cancellation, overflow/underflow, domain restrictions and conditioning when relevant. Justify metamorphic properties, convergence rates and conservation laws from the actual method; do not invent invariants for stochastic, dissipative or approximate systems. Test refinement against the predicted regime, not a single favorable mesh or step size.

Floating-point reductions may depend on order, vectorization, fused operations, compiler flags and thread scheduling. Specify whether reproducibility means bitwise identity, tolerance-bounded agreement or a statistical criterion. Stochastic methods require seed/stream management and justified statistical tests; one matching seed does not validate a distribution. Do not enable fast-math-like options or change precision without assessing their effect on invariants and error bounds.

Independent reference evidence may be an analytical solution, a separately implemented trusted method, validated archived outputs or higher-precision calculations with documented uncertainty. A Python reference is useful only if its semantics, dtype, ordering and independence are established. Distinguish reference uncertainty from implementation failure and preserve minimal failing inputs.

Rust floating-point behavior and epsilon definitions: [official f64 reference](https://doc.rust-lang.org/std/primitive.f64.html). Repository-specific mathematical sources and acceptance thresholds remain project-owned.
