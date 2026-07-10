dimip.lst: dimip.bin dimip.notes dimip.sym
	./disasm.sh > $@

%.cov: %.txt coverage.sh dimip.b6
	./coverage.sh $<

subtask.cov: subtask.exp
	./subtask.exp

combined.cov: composite.cov subtask.cov macro.cov mkp.cov
	./combine_coverage.py $^ > $@

dimip.uncov: dimip.lst combined.cov
	./uncovered_commands.py > $@
	wc -l $@

clean:
	rm -f *.lst *.cov *.uncov
