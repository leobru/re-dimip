dimip.lst: dimip.bin dimip.notes dimip.sym
	./disasm.sh > $@

%.cov: %.txt coverage.sh dimip.b6
	./coverage.sh $<

bd.cov: bd.setup

subtask.cov: subtask.exp
	./subtask.exp

combined.cov: composite.cov subtask.cov macro.cov mkp.cov bd.cov
	./combine_coverage.py $^ | grep '^0[2-5]...:' > $@

dimip.uncov: dimip.lst combined.cov
	./uncovered_commands.py > $@
	wc -l $@

re-dimip.bin: re-dimip.be
	./asm.pl $<

dimip.dump:
	besmtool dump 2048 --start=044 --length=2 > $@

re-dimip.dump:
	./asm.pl re-dimip.be
	besmtool dump 1234 --start=044 --length=2 > $@

check: dimip.bin re-dimip.bin
	cmp $^ && echo SUCCESS

clean:
	rm -f *.lst *.cov *.uncov
