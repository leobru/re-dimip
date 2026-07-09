#!/usr/bin/env python3
# Combine dispak coverage maps.
#
# Usage:
#   ./combine_coverage.py cov1 cov2 [cov3 ...] > cov-combined
#
# Coverage lines are expected to look like:
#   03021: L
#   03022: LR
#   03023: --
#
# The result is the per-half union: a left/right command is marked covered if
# it is covered in any input file.

import argparse
import re
import sys


LINE_RE = re.compile(r"^([0-7]{4,5}):\s*([LR -]{2})\s*$")


def read_coverage(path):
    rows = []
    with open(path, encoding="utf-8") as f:
        for lineno, raw in enumerate(f, 1):
            line = raw.rstrip("\n")
            m = LINE_RE.match(line)
            if not m:
                raise ValueError(f"{path}:{lineno}: bad coverage line: {line!r}")
            addr = int(m.group(1), 8)
            status = m.group(2)
            rows.append((addr, status[0] == "L", status[1] == "R"))
    return rows


def format_status(left, right):
    if left and right:
        return "LR"
    if left:
        return "L "
    if right:
        return " R"
    return "--"


def main():
    parser = argparse.ArgumentParser(
        description="Combine two or more covexp-style coverage files."
    )
    parser.add_argument("coverage", nargs="+", help="coverage files to combine")
    args = parser.parse_args()

    try:
        combined = read_coverage(args.coverage[0])
        for path in args.coverage[1:]:
            rows = read_coverage(path)
            if len(rows) != len(combined):
                raise ValueError(
                    f"{path}: address count {len(rows)} differs from "
                    f"{args.coverage[0]} count {len(combined)}"
                )
            for i, ((addr, left, right), (base_addr, base_left, base_right)) in enumerate(
                zip(rows, combined), 1
            ):
                if addr != base_addr:
                    raise ValueError(
                        f"{path}:{i}: address {addr:05o} does not match "
                        f"{args.coverage[0]} address {base_addr:05o}"
                    )
                combined[i - 1] = (base_addr, base_left or left, base_right or right)

        for addr, left, right in combined:
            print(f"{addr:05o}: {format_status(left, right)}")
    except BrokenPipeError:
        sys.exit(1)
    except OSError as e:
        sys.stderr.write(f"combine_coverage.py: {e}\n")
        sys.exit(1)
    except ValueError as e:
        sys.stderr.write(f"combine_coverage.py: {e}\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
