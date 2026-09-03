"""Execute every ALAM regression assertion, including pytest-style test functions.

GitHub Actions historically invoked many ``test_*.py`` modules with plain ``python``.
That only executes tests which happen to provide their own ``__main__`` runner. This
small dependency-free harness makes assertion execution the invariant instead of a
per-file convention.
"""

from __future__ import annotations

import inspect
import runpy
from pathlib import Path


TEST_DIR = Path(__file__).resolve().parent


def _required_parameters(function) -> list[str]:
    required = []
    for parameter in inspect.signature(function).parameters.values():
        if parameter.kind in (parameter.VAR_POSITIONAL, parameter.VAR_KEYWORD):
            continue
        if parameter.default is parameter.empty:
            required.append(parameter.name)
    return required


def main() -> None:
    files = sorted(TEST_DIR.glob("test_*.py"))
    if not files:
        raise RuntimeError("No ALAM regression tests were discovered.")

    executed = 0
    for path in files:
        namespace = runpy.run_path(str(path), run_name=f"alam_regression_{path.stem}")
        tests = sorted(
            (name, value)
            for name, value in namespace.items()
            if name.startswith("test_") and callable(value)
        )
        for name, test in tests:
            required = _required_parameters(test)
            if required:
                raise RuntimeError(
                    f"{path.name}:{name} requires unsupported test parameters: "
                    + ", ".join(required)
                )
            try:
                test()
            except Exception as exc:
                raise AssertionError(f"Regression failed: {path.name}:{name}") from exc
            executed += 1

    if executed == 0:
        raise RuntimeError("ALAM regression files contained no executable test functions.")
    print(f"Executed {executed} ALAM regression assertions across {len(files)} files.")


if __name__ == "__main__":
    main()
