#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from mna_nozzle_analysis.synthetic import write_synthetic_case


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("destination")
    args = parser.parse_args()
    output = write_synthetic_case(args.destination)
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

