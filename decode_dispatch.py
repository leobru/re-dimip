#!/usr/bin/env python3
# Decode the DIMIP directive dispatch table (addresses 02274..02325 in dimip.bin).
#
# Each 48-bit entry packs:  [key: high 24 bits = 3 GOST chars] [flags] [handler: low 15 bits]
# The scan loop at G03222 right-shifts the entry by 24 (СДА 64+24) to bring the key down,
# XORs it with the parsed directive token, and on a match jumps to the handler (low 15 bits).
#
# GOST 6-chars/word table taken from disbesm6's encoding.c (gost_to_unicode_cyr).

GOST = {0o0:'0',0o1:'1',0o2:'2',0o3:'3',0o4:'4',0o5:'5',0o6:'6',0o7:'7',
        0o10:'8',0o11:'9',0o12:'+',0o13:'-',0o14:'/',0o15:',',0o16:'.',0o17:' ',
        0o20:'e',0o21:'^',0o22:'(',0o23:')',0o24:'*',0o25:'=',0o26:';',0o27:'[',
        0o30:']',0o31:'*',0o32:"'",0o33:"'",0o34:'#',0o35:'<',0o36:'>',0o37:':'}
for i,c in enumerate("АБВГДЕЖЗИЙКЛМНОПРСТУФХЦЧШЩЫЬЭЮЯ"):
    GOST[0o40+i] = c
GOST[0o77] = 'D'
for i,c in enumerate("FGIJLNQRSUVWZ"):
    GOST[0o100+i] = c

def decode(b):
    return ''.join(GOST.get(x,'·') for x in b if x != 0)

def main():
    data = open('dimip.bin','rb').read()
    def word(a):
        i = (a - 0o2000) * 6
        return int.from_bytes(data[i:i+6],'big')
    print("key    flags   handler")
    for a in range(0o2274, 0o2326):
        w = word(a)
        hi = (w >> 24) & 0xFFFFFF
        key = decode([(hi>>16)&0xFF, (hi>>8)&0xFF, hi&0xFF])
        flags = (w >> 15) & 0o777
        handler = w & 0o77777
        print(f"  {key:<4} {flags:03o}     G{handler:05o}")

if __name__ == '__main__':
    main()
