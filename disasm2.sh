#!/bin/sh
# Reproducible disassembly of the DIMIP "manual" build (dimip2.bin).
# Same 2048-word BESM-6 image loaded at octal 02000 as dimip.bin, but a
# different build whose МКП directive set matches manual §6.2.7 more closely
# (adds SIZ, UNТ; drops the dimip-only СОN/СНЕ/LАВ/ЕND).  See DIMIP2-notes.md.
#
# Uses trace2 when present to seed dynamic code discovery.  In the Makefile
# flow, trace2 is derived from combined2.cov so coverage tests directly improve
# disassembly without needing a separate traced dispak run.
set -e
DIS=${DISBESM6:-/usr/local/bin/disbesm6}
SYM=${SYM:-dimip2.sym}
NOTES=${NOTES:-dimip2.notes}
TRACEOPT=""
[ -f "${TRACE:-trace2}" ] && TRACEOPT="--trace=${TRACE:-trace2}"

if [ -f "$NOTES" ]; then
    "$DIS" -b -a2000 -e2000 $TRACEOPT -n "$SYM" dimip2.bin | ./annotate.py "$NOTES"
else
    exec "$DIS" -b -a2000 -e2000 $TRACEOPT -n "$SYM" dimip2.bin
fi
