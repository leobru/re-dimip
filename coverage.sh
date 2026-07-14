#!/bin/sh
set -e
base=`basename "$1" .txt`
if [ -x "./$base.setup" ]; then
	"./$base.setup"
fi
timeout 10 dispak -p --coverage=$base.cov dimip.b6 < $1 >$base.out
echo -n "Covered words: "; grep -c '^0[2-5]...: L' $base.cov
