#!/usr/bin/env python3
# Count covered half-word locations that are unique to each coverage file.
#
# Usage:
#   ./unique_coverage.py file1.cov file2.cov [...]
#
# A location is an address half: 03021L or 03021R.  A location is unique to a
# file if it is covered in that file and uncovered in every other input file.

import argparse
import re
import sys


LINE_RE = re.compile(r"^([0-7]{4,5}):\s*([LR -]{2})\s*$")


def read_covered_locations(path):
    locations = set()
    with open(path, encoding="utf-8") as f:
        for lineno, raw in enumerate(f, 1):
            line = raw.rstrip("\n")
            m = LINE_RE.match(line)
            if not m:
                raise ValueError(f"{path}:{lineno}: bad coverage line: {line!r}")
            addr = int(m.group(1), 8)
            status = m.group(2)
            if status[0] == "L":
                locations.add((addr, "L"))
            if status[1] == "R":
                locations.add((addr, "R"))
    return locations


def main():
    parser = argparse.ArgumentParser(
        description="Count covered locations unique to each coverage file."
    )
    parser.add_argument("coverage", nargs="+", help="coverage files to compare")
    args = parser.parse_args()

    try:
        covered_by_file = [(path, read_covered_locations(path)) for path in args.coverage]
        location_counts = {}
        for _path, locations in covered_by_file:
            for location in locations:
                location_counts[location] = location_counts.get(location, 0) + 1

        print("file covered unique")
        for path, locations in covered_by_file:
            unique = sum(1 for location in locations if location_counts[location] == 1)
            print(f"{path} {len(locations)} {unique}")
    except BrokenPipeError:
        sys.exit(1)
    except OSError as e:
        sys.stderr.write(f"unique_coverage.py: {e}\n")
        sys.exit(1)
    except ValueError as e:
        sys.stderr.write(f"unique_coverage.py: {e}\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
