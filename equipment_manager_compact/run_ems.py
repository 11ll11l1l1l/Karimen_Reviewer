from __future__ import annotations

import sys

from loader import install


def main() -> int:
    install()
    if len(sys.argv) > 1 and sys.argv[1].lower() in {"cli", "--cli"}:
        sys.argv.pop(1)
        from ems_cli import main as cli_main
        return int(cli_main() or 0)

    from smart_app import main as gui_main
    result = gui_main()
    return int(result or 0) if isinstance(result, int) else 0


if __name__ == "__main__":
    raise SystemExit(main())
