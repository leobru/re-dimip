#!/usr/bin/env python3
# Decode a BESM-6 Э70 disk-exchange control word, per dispak ddio() / defs.h.
import sys

def fields(w):
    b = [(w >> (8*(5-i))) & 0xff for i in range(6)]  # w_b[0..5], MSB first
    def left():
        struct = b[0] & 8
        exp    = b[0] & 4
        reg    = b[0] >> 4
        if struct:
            op = (((b[1] >> 7) | (b[0] << 1)) & 0xf) | 0o100
            addr = ((b[1] << 8) | b[2]) & 0x7fff
        else:
            op = ((b[1] >> 4) | (b[0] << 4)) & 0x3f
            addr = (((b[1] << 8) | b[2]) & 0xfff) | (0o70000 if exp else 0)
        return reg, op, addr
    def right():
        struct = b[3] & 8
        exp    = b[3] & 4
        reg    = b[3] >> 4
        if struct:
            op = (((b[4] >> 7) | (b[3] << 1)) & 0xf) | 0o100
            addr = ((b[4] << 8) | b[5]) & 0x7fff
        else:
            op = ((b[4] >> 4) | (b[3] << 4)) & 0x3f
            addr = (((b[4] << 8) | b[5]) & 0xfff) | (0o70000 if exp else 0)
        return reg, op, addr
    return left(), right()

def decode(w):
    (lreg, lop, laddr), (rreg, rop, raddr) = fields(w)
    page = (laddr & 0o3700) << 4          # адрес листа (memory)
    u    = rop & 0o77                     # disk/LUN number
    if u < 0o30 or u >= 0o70:
        zone = raddr & 0o37; ztype='тракт барабана'
    else:
        zone = raddr & 0o7777; ztype='зона диска'
    phys = bool(lop & 4)
    sect = bool(lreg & 8)
    if sect:
        op = 'СЕКТОР'
    elif lop & 0o10:
        op = 'ЧТЕНИЕ зоны'
    else:
        op = 'ЗАПИСЬ зоны'
    chk = bool(lop & 1)
    return (f"L[reg={lreg:o} op={lop:03o} addr={laddr:05o}] "
            f"R[reg={rreg:o} op={rop:03o} addr={raddr:05o}] => "
            f"{op}{' ФИЗ' if phys else ''}{' +КС' if chk else ''}, "
            f"ЛУН/диск={u:o}, {ztype}={zone:o} (мем.лист 0{page:o})")

for a in sys.argv[1:]:
    w = int(a, 8)
    print(f"{a} = {decode(w)}")
