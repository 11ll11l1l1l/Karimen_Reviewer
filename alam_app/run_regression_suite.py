"""Execute every ALAM regression assertion, including lightweight fixture tests.

GitHub Actions historically invoked many ``test_*.py`` modules with plain ``python``.
That only executes tests which happen to provide their own ``__main__`` runner. This
small dependency-free harness makes assertion execution the invariant instead of a
per-file convention.

The harness intentionally supports only fixtures that it can implement safely without
pulling a second test framework into the production dependency set. Unsupported fixture
parameters still fail closed so a newly added test can never be silently skipped.
"""

from __future__ import annotations

import inspect
import runpy
from pathlib import Path
from typing import Any


TEST_DIR = Path(__file__).resolve().parent


class _MonkeyPatch:
    """Minimal pytest-compatible ``setattr`` fixture with guaranteed restoration.

    ALAM regression tests use monkeypatching to isolate Streamlit/browser state. The
    CI harness must restore every mutation even when an assertion fails; otherwise a
    test can contaminate later modules and create order-dependent false results.
    """

    def __init__(self) -> None:
        self._undo: list[tuple[Any, str, Any]] = []

    def setattr(self, target: Any, name: str, value: Any) -> None:
        original = getattr(target, name)
        self._undo.append((target, name, original))
        setattr(target, name, value)

    def undo(self) -> None:
        while self._undo:
            target, name, original = self._undo.pop()
            setattr(target, name, original)


def _required_parameters(function) -> list[str]:
    required = []
    for parameter in inspect.signature(function).parameters.values():
        if parameter.kind in (parameter.VAR_POSITIONAL, parameter.VAR_KEYWORD):
            continue
        if parameter.default is parameter.empty:
            required.append(parameter.name)
    return required


def _execute_test(path: Path, name: str, test) -> None:
    required = _required_parameters(test)
    unsupported = [parameter for parameter in required if parameter != "monkeypatch"]
    if unsupported:
        raise RuntimeError(
            f"{path.name}:{name} requires unsupported test parameters: "
            + ", ".join(unsupported)
        )

    monkeypatch = _MonkeyPatch() if "monkeypatch" in required else None
    kwargs = {"monkeypatch": monkeypatch} if monkeypatch is not None else {}
    try:
        test(**kwargs)
    except Exception as exc:
        raise AssertionError(f"Regression failed: {path.name}:{name}") from exc
    finally:
        if monkeypatch is not None:
            monkeypatch.undo()


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
            _execute_test(path, name, test)
            executed += 1

    if executed == 0:
        raise RuntimeError("ALAM regression files contained no executable test functions.")
    print(f"Executed {executed} ALAM regression assertions across {len(files)} files.")


if __name__ == "__main__":
    main()
