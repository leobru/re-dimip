#!/bin/sh
set -e
input=$1
base=`basename "$input" .txt`
image=${2:-dimip.b6}
shift
if [ $# -gt 0 ]; then
	shift
fi
if [ -x "./$base.setup" ]; then
	"./$base.setup"
fi
timeout 10 dispak -p "$@" --coverage=$base.cov "$image" < "$input" >$base.out
echo -n "Covered words: "; grep -c '^0[2-5]...: L' $base.cov
