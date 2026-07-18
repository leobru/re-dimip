COVERAGE_TXT = composite macro mkp bd fact context seek listing admin bilist convert grow linenum sit divzero
COVERAGE_OTHER = subtask setup
COVERAGE_TARGETS = $(COVERAGE_TXT:%=%.cov) $(COVERAGE_OTHER:%=%.cov)
COVERAGE2_TXT = composite2 mkp-manual bd2 macro2 bilist2 loop grow2 linenum2 listing2 convert2 context2 seek2 admin2 divzero2 sit2
COVERAGE2_TXT_TARGETS = $(COVERAGE2_TXT:%=%.cov)
COVERAGE2_OTHER = subtask2
COVERAGE2_TARGETS = $(COVERAGE2_TXT_TARGETS) $(COVERAGE2_OTHER:%=%.cov)

dimip.lst: dimip.bin dimip.notes dimip.sym
	./disasm.sh > $@

dimip2.lst: dimip2.bin dimip2.notes dimip2.sym trace2
	./disasm2.sh > $@

trace2: combined2.cov
	awk '$$2 != "--" { print $$1 " coverage" }' $< > $@

%.cov: %.txt coverage.sh dimip.b6
	./coverage.sh $<

$(COVERAGE2_TXT_TARGETS): %.cov: %.txt coverage.sh dimip2248.b6
	./coverage.sh $< dimip2248.b6 -x

bd.cov: bd.setup

subtask.cov: subtask.exp
	./subtask.exp

subtask2.cov: subtask2.exp dimip2248.b6
	./subtask2.exp > subtask2.out 2> subtask2.err

setup.cov: setup.b6
	dispak -p --coverage=$@ setup.b6 < /dev/null > setup.out

combined.cov: $(COVERAGE_TARGETS)
	./combine_coverage.py $^ | grep '^0[2-5]...:' > $@

combined2.cov: $(COVERAGE2_TARGETS)
	./combine_coverage.py $^ | grep '^0[2-5]...:' > $@

dimip.uncov: dimip.lst combined.cov
	./uncovered_commands.py > $@
	wc -l $@

dimip2.uncov: dimip2.lst combined2.cov
	./uncovered_commands.py dimip2.lst combined2.cov > $@
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

unique: $(COVERAGE_TARGETS)
	./unique_coverage.py $^

unique2: $(COVERAGE2_TARGETS)
	./unique_coverage.py $^

clean:
	rm -f *.lst *.cov *.uncov
