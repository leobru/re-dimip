#!/bin/sh
# Reproducible disassembly of the DIMIP monitor binary.
#
# dimip.bin is a 2048-word (octal 04000) BESM-6 image loaded at octal 02000.
# It is reached from the dimip.b6 job deck (load at 6000, Э70 6000, transfer to 02000).
#
# disbesm6 does its own flow analysis but cannot follow the computed jumps that
# drive DIMIP's directive dispatcher, so it leaves indirectly-reached code marked
# as data ("конд").  We feed every address the reference execution trace actually
# executed as an extra entry point (-e); those are guaranteed-code, which forces
# correct decoding of every routine the trace reaches.  See DIMIP-analysis.md.
#
# Output: dimip.lst

set -e
DIS=${DISBESM6:-/home/leob/git/leobru/dispak-tools/disbesm6}
TRACE=${TRACE:-trace}
SYM=${SYM:-dimip.sym}

# Entry points confirmed by пв/vjm calls in the trace
CALLS="-e2070 -e3041 -e3323 -e3335 -e3507 -e5216"

# Every distinct address executed in the trace within the module (02000..05777)
TRACE_ENTRIES=$(grep -oE '^[0-9]{5}:' "$TRACE" | tr -d ':' | sort -u | \
    awk '{n=strtonum("0"$1); if (n>=01000 && n<=05777) printf "-e%s ", $1}')

exec "$DIS" -b -a2000 -e2000 $CALLS $TRACE_ENTRIES -n "$SYM" dimip.bin
