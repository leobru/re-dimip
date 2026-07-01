#!/usr/bin/env python3
# Annotate a disbesm6 listing.
#
#   disbesm6 ... | ./annotate.py dimip.notes > dimip.lst
#
# Reads the listing from stdin and an annotation file (argv[1]), writes the
# annotated listing to stdout.
#
# Annotation file lines (addresses are octal, as printed by disbesm6):
#   #...                comment, ignored
#   <addr>  > <text>    full-line comment, emitted as "* <text>" ABOVE <addr>'s line
#                       (repeat for multi-line blocks; lines stack in file order)
#   <addr>  ; <text>    inline comment, appended right of the LEFT instruction's operand
#   <addr>r ; <text>    inline comment on the RIGHT instruction of <addr>
#
# A BESM-6 word holds two instructions; "<addr>" is the left one (or a data
# word), "<addr>r" the right one.

import sys, re

def main():
    if len(sys.argv) < 2:
        sys.stderr.write("usage: annotate.py <annotation-file> < listing\n")
        sys.exit(1)

    blocks = {}    # addr -> [text, ...]
    inline = {}    # (addr, 'L'|'R') -> text
    with open(sys.argv[1], encoding='utf-8') as f:
        for raw in f:
            s = raw.rstrip('\n').strip()
            if not s or s.startswith('#'):
                continue
            m = re.match(r'(\d+)([rR]?)\s+([>;])\s?(.*)$', s)
            if not m:
                sys.stderr.write("annotate: skipping bad line: %s\n" % s)
                continue
            addr = int(m.group(1), 8)
            half = 'R' if m.group(2) else 'L'
            kind, text = m.group(3), m.group(4)
            if kind == '>':
                blocks.setdefault(addr, []).append(text)
            else:
                inline[(addr, half)] = text

    addr_re = re.compile(r'^\s*(\d{4,5})[ :]')
    cur_addr = None
    expect_right = False
    w = sys.stdout.write
    for raw in sys.stdin:
        line = raw.rstrip('\n')
        m = addr_re.match(line)
        if m:
            addr = int(m.group(1), 8)
            for t in blocks.get(addr, []):
                w('*' + (' ' + t if t else '') + '\n')
            # instruction (spaced octal -> has a right half) vs data word
            field = line[m.end():].split('\t', 1)[0]
            cur_addr = addr
            expect_right = ' ' in field.strip()
            if (addr, 'L') in inline:
                line += '\t' + inline[(addr, 'L')]
            w(line + '\n')
        else:
            if expect_right and line.strip():
                if (cur_addr, 'R') in inline:
                    line += '\t' + inline[(cur_addr, 'R')]
                expect_right = False
            w(line + '\n')

if __name__ == '__main__':
    main()
