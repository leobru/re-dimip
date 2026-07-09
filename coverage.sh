#!/bin/sh
base=`basename "$1" .txt`
dispak -p --coverage=$base.cov dimip.b6 < $1 >$base.out
echo -n "Covered words: "; grep -c '^0[2-5]...: L' $base.cov
