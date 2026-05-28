"""Benchmark: deepcopy vs _safe_default for default parameter values.

Run with: uv run python tests/benchmarks/bench_safe_default.py
"""

import timeit
from copy import deepcopy

from fastapi.dependencies.utils import _IMMUTABLE_TYPES, _safe_default

# --- Test values ---
IMMUTABLE_DEFAULTS = {
    "None": None,
    "bool (True)": True,
    "int (42)": 42,
    "float (3.14)": 3.14,
    "str ('hello')": "hello",
    "bytes (b'data')": b"data",
}

MUTABLE_DEFAULTS = {
    "list ([])": [],
    "list ([1, 2, 3])": [1, 2, 3],
    "dict ({})": {},
    "dict ({'a': 1})": {"a": 1},
    "set ({1, 2})": {1, 2},
    "tuple ((1, 2, 3))": (1, 2, 3),
    "frozenset ({1, 2})": frozenset({1, 2}),
}

ITERATIONS = 100_000


def benchmark_single(label: str, value, iterations: int = ITERATIONS):
    t_deepcopy = timeit.timeit(lambda: deepcopy(value), number=iterations)
    t_safe = timeit.timeit(lambda: _safe_default(value), number=iterations)
    speedup = t_deepcopy / t_safe if t_safe > 0 else float("inf")
    return {
        "label": label,
        "deepcopy_us": t_deepcopy / iterations * 1_000_000,
        "safe_default_us": t_safe / iterations * 1_000_000,
        "speedup": speedup,
    }


def simulate_endpoint_defaults(use_safe: bool, iterations: int = ITERATIONS):
    """Simulate resolving defaults for a typical endpoint with 5 optional params,
    where 3 are missing (page=1, sort=None, order=None)."""
    defaults = [None, 1, None]  # 3 missing optional params

    if use_safe:
        func = _safe_default
    else:
        func = deepcopy

    def resolve_defaults():
        for d in defaults:
            func(d)

    return timeit.timeit(resolve_defaults, number=iterations)


def main():
    print("=" * 78)
    print("Benchmark: deepcopy() vs _safe_default() for parameter defaults")
    print("=" * 78)
    print(f"Iterations per test: {ITERATIONS:,}\n")

    print(f"{'Type':<28} {'deepcopy (µs)':>14} {'_safe_default (µs)':>18} {'Speedup':>10}")
    print("-" * 78)

    # Immutable types
    print("\n  IMMUTABLE TYPES (fast-path: identity return)")
    results_immutable = []
    for label, value in IMMUTABLE_DEFAULTS.items():
        r = benchmark_single(label, value)
        results_immutable.append(r)
        print(f"  {r['label']:<26} {r['deepcopy_us']:>14.3f} {r['safe_default_us']:>18.3f} {r['speedup']:>9.1f}x")

    # Mutable types
    print("\n  MUTABLE TYPES (deepcopy preserved for safety)")
    results_mutable = []
    for label, value in MUTABLE_DEFAULTS.items():
        r = benchmark_single(label, value)
        results_mutable.append(r)
        print(f"  {r['label']:<26} {r['deepcopy_us']:>14.3f} {r['safe_default_us']:>18.3f} {r['speedup']:>9.1f}x")

    # Endpoint simulation
    print("\n" + "-" * 78)
    print("\n  ENDPOINT SIMULATION (3 missing optional params per request)")

    t_old = simulate_endpoint_defaults(use_safe=False)
    t_new = simulate_endpoint_defaults(use_safe=True)
    speedup = t_old / t_new if t_new > 0 else float("inf")

    print(f"  deepcopy (before):   {t_old / ITERATIONS * 1_000_000:>10.3f} µs/request")
    print(f"  _safe_default (after): {t_new / ITERATIONS * 1_000_000:>10.3f} µs/request")
    print(f"  Speedup:             {speedup:>10.1f}x")

    # Summary
    avg_immutable_speedup = sum(r["speedup"] for r in results_immutable) / len(results_immutable)
    print(f"\n{'=' * 78}")
    print(f"Average speedup for immutable types: {avg_immutable_speedup:.1f}x")
    print(f"Endpoint simulation speedup:         {speedup:.1f}x")
    print(f"{'=' * 78}")


if __name__ == "__main__":
    main()
