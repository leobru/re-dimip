#!/bin/sh
# Reproducible disassembly of the DIMIP monitor binary.
#
# dimip.bin is a 2048-word (octal 04000) BESM-6 image loaded at octal 02000.
# It is reached from the dimip.b6 job deck (load at 6000, Э70 6000, transfer to 02000).
#
# disbesm6 does its own flow analysis but cannot follow the computed jumps that
# drive DIMIP's dispatchers, so indirectly-reached code would be left as data
# ("конд").  Two disbesm6 features close that gap (see DIMIP-analysis.md):
#   --trace=FILE      seeds every address executed in the reference trace as a
#                     guaranteed-code entry point (the init path and main loop);
#   sym type "J"      marks the dispatch tables (ТАБДИР, АДРКОМ) so the handler
#                     addresses packed in their words become entry points too —
#                     this discovers the directive and script-command handlers,
#                     including ones the trace never exercised.
#
# Output: dimip.lst

set -e
DIS=${DISBESM6:-/home/leob/git/leobru/dispak-tools/disbesm6}
TRACE=${TRACE:-trace}
SYM=${SYM:-dimip.sym}
NOTES=${NOTES:-dimip.notes}

# Disassemble; pipe through annotate.py when an annotation file is present.
if [ -f "$NOTES" ]; then
    "$DIS" -b -a2000 -e2000 --trace="$TRACE" -n "$SYM" dimip.bin | ./annotate.py "$NOTES"
else
    exec "$DIS" -b -a2000 -e2000 --trace="$TRACE" -n "$SYM" dimip.bin
fi
