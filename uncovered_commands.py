#!/usr/bin/env python3
# List disassembled DIMIP commands not reached according to a dispak coverage map.
#
# Usage:
#   ./uncovered_commands.py [dimip.lst [combined.cov]]
#
# Coverage lines are expected to look like:
#   03021: L
#   03022: LR
#   03023: --
#
# A BESM-6 word contains left and right commands.  The listing prints the left
# command with the word address and the right command on the following indented
# line, so this script maps coverage halves back onto the listing text.

import argparse
import re
import sys

PSEUDO_OPS = {"конд", "конк", "экв", "ФИНИШ"}


def read_coverage(path):
    coverage = {}
    line_re = re.compile(r"^([0-7]{4,5}):\s*([LR -]{2})\s*$")
    with open(path, encoding="utf-8") as f:
        for lineno, raw in enumerate(f, 1):
            line = raw.rstrip("\n")
            m = line_re.match(line)
            if not m:
                raise ValueError(f"{path}:{lineno}: bad coverage line: {line!r}")
            coverage[int(m.group(1), 8)] = m.group(2)
    return coverage


def looks_like_half_command(line):
    return re.match(r"^\s+[0-7]{2}\s+[0-7]{2,3}\s+[0-7]{1,5}\b", line) is not None


def listing_mnemonic(line):
    fields = [field.strip() for field in line.split("\t") if field.strip()]
    if len(fields) < 2:
        return None

    # The first field is the address/machine-code column.  A label, if present,
    # is the next field; the mnemonic is the first field after that which is not
    # a label-looking token.
    for field in fields[1:]:
        if re.match(r"^[A-ZА-Я_][A-ZА-Я0-9_+-]*$", field):
            continue
        return field
    return fields[1]


def iter_listing_commands(path):
    left_re = re.compile(r"^\s*([0-7]{4,5})(?::)?")
    right_addr = None

    with open(path, encoding="utf-8") as f:
        for lineno, raw in enumerate(f, 1):
            line = raw.rstrip("\n")

            m = left_re.match(line)
            if m and looks_like_half_command(line[m.end() :]):
                right_addr = int(m.group(1), 8)
                mnemonic = listing_mnemonic(line)
                if mnemonic and mnemonic not in PSEUDO_OPS:
                    yield right_addr, "L", lineno, line
                continue

            if right_addr is not None and looks_like_half_command(line):
                mnemonic = listing_mnemonic(line)
                if mnemonic and mnemonic not in PSEUDO_OPS:
                    yield right_addr, "R", lineno, line
                right_addr = None
                continue

            right_addr = None


def main():
    parser = argparse.ArgumentParser(
        description="List dimip.lst commands whose coverage half is not marked covered."
    )
    parser.add_argument("listing", nargs="?", default="dimip.lst")
    parser.add_argument("coverage", nargs="?", default="combined.cov")
    parser.add_argument(
        "--only-words",
        action="store_true",
        help="only report commands in words whose coverage status is exactly '--'",
    )
    args = parser.parse_args()

    try:
        coverage = read_coverage(args.coverage)
        for addr, half, lineno, line in iter_listing_commands(args.listing):
            status = coverage.get(addr)
            if status is None:
                continue
            if args.only_words:
                uncovered = status == "--"
            elif half == "L":
                uncovered = status[0] != "L"
            else:
                uncovered = status[1] != "R"
            if uncovered:
                # print(f"{addr:05o}{half} {status} {args.listing}:{lineno}: {line}")
                print(f"{addr:05o}{half} {status}: {line}")
    except BrokenPipeError:
        sys.exit(1)
    except OSError as e:
        sys.stderr.write(f"uncovered_commands.py: {e}\n")
        sys.exit(1)
    except ValueError as e:
        sys.stderr.write(f"uncovered_commands.py: {e}\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
