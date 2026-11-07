"""Command line.

  python -m app.cli refresh          download data, train, backtest
  python -m app.cli backtest         retrain + backtest on stored data (no download)
  python -m app.cli export <dir>     refresh, then write static JSON for the Pages build
"""
from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

from . import service


def main(argv: list[str]) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    flags = {a for a in argv if a.startswith("--")}
    argv = [a for a in argv if not a.startswith("--")]
    cmd = argv[0] if argv else "refresh"
    if cmd == "refresh":
        print(json.dumps(service.refresh(), indent=2))
    elif cmd == "backtest":
        service.refresh(fetch=False)
        print(json.dumps(service.backtest_report(), indent=2))
    elif cmd == "export" and len(argv) == 2:
        from .export import export
        fetch = "--no-fetch" not in flags
        print(json.dumps(service.refresh(fetch=fetch), indent=2))
        print(json.dumps(export(Path(argv[1])), indent=2))
    else:
        print(__doc__)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
