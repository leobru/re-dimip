#!/usr/bin/env python3
"""Decode a DISPАK raw output stream into Unicode text.

The byte grammar follows DIMIP's ДИРБ reader around 05072-05115:

* raw `pzNNN.raw` is a sequence of 1536-byte stream chunks, each with a
  12-byte non-stream header;
* byte zero terminates the stream;
* bytes below octal 0141 are GOST text codes biased by +1;
* bytes at/above octal 0141 are stream controls.

The control formatting is intentionally conservative, but it implements the
visible cases in G05107: line finish, stream end, repeat, and absolute-column
spacing.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


# GOST-10859 cyrillic table, copied in numeric form from dispak/mkarfa.py.
GOST_TO_UNICODE = [0] * 256
_G2U = [
    0x30, 0x31, 0x32, 0x33, 0x34, 0x35, 0x36, 0x37,
    0x38, 0x39, 0x2B, 0x2D, 0x2F, 0x2C, 0x2E, 0x20,
    0x23E8, 0x2191, 0x28, 0x29, 0xD7, 0x3D, 0x3B, 0x5B,
    0x5D, 0x2A, 0x2018, 0x2019, 0x2260, 0x3C, 0x3E, 0x3A,
    0x0410, 0x0411, 0x0412, 0x0413, 0x0414, 0x0415, 0x0416, 0x0417,
    0x0418, 0x0419, 0x041A, 0x041B, 0x041C, 0x041D, 0x041E, 0x041F,
    0x0420, 0x0421, 0x0422, 0x0423, 0x0424, 0x0425, 0x0426, 0x0427,
    0x0428, 0x0429, 0x042B, 0x042C, 0x042D, 0x042E, 0x042F, 0x44,
    0x46, 0x47, 0x49, 0x4A, 0x4C, 0x4E, 0x51, 0x52,
    0x53, 0x55, 0x56, 0x57, 0x5A, 0x203E, 0x2A7D, 0x2A7E,
    0x2228, 0x2227, 0x2283, 0xAC, 0xF7, 0x2261, 0x25, 0x25C7,
    0x7C, 0x2015, 0x5F, 0x21, 0x22, 0x042A, 0xB0, 0x2032,
]
for _i, _v in enumerate(_G2U):
    GOST_TO_UNICODE[_i] = _v
GOST_TO_UNICODE[0o174] = 0x2424
GOST_TO_UNICODE[0o175] = 0x5C


def gost_to_text(code: int) -> str:
    value = GOST_TO_UNICODE[code & 0xFF]
    if value:
        return chr(value)
    return f"<{code:03o}>"


class StreamReader:
    def __init__(self, raw: bytes, *, chunk_bytes: int, skip_chunk_bytes: int):
        self.raw = raw
        self.chunk_bytes = chunk_bytes
        self.skip_chunk_bytes = skip_chunk_bytes
        self.pos = skip_chunk_bytes

    def next(self) -> int | None:
        while self.pos < len(self.raw):
            in_chunk = self.pos % self.chunk_bytes
            if in_chunk < self.skip_chunk_bytes:
                self.pos += self.skip_chunk_bytes - in_chunk
                continue
            value = self.raw[self.pos]
            self.pos += 1
            return value
        return None

    def skip_to_next_chunk(self) -> None:
        self.pos = ((self.pos + self.chunk_bytes - 1) // self.chunk_bytes) * self.chunk_bytes
        self.pos += self.skip_chunk_bytes


def decode_stream(data: bytes, args: argparse.Namespace) -> str:
    out: list[str] = []
    col = 0
    current = ""
    stream = StreamReader(
        data,
        chunk_bytes=args.chunk_bytes,
        skip_chunk_bytes=args.skip_chunk_bytes,
    )

    while True:
        byte = stream.next()
        if byte is None:
            break
        if byte == 0:
            break

        if byte < 0o141:
            current = gost_to_text(byte - 1)
            out.append(current)
            col += 1
            continue

        if byte in (0o141, 0o174):
            # Next 0400-word quarter of the stream zone; no visible text.
            if args.show_controls:
                out.append(f"<{byte:03o}>")
            stream.skip_to_next_chunk()
            continue

        if 0o142 <= byte <= 0o160 or byte == 0o176:
            if args.keep_blank_lines or not out or out[-1] != "\n":
                out.append("\n")
            col = 0
            current = ""
            continue

        if byte == 0o175:
            break

        if byte == 0o177:
            repeat = stream.next()
            if repeat is None:
                break
            if args.show_controls:
                out.append(f"<177,{repeat:03o}>")
            if current:
                out.append(current * repeat)
                col += repeat
            continue

        target = byte - 0o200
        if args.show_controls:
            out.append(f"<{byte:03o}>")
        if target > col:
            out.append(" " * (target - col))
            col = target

    return "".join(out)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="Convert a pzNNN.raw output stream to Unicode text."
    )
    parser.add_argument("raw_file", type=Path)
    parser.add_argument(
        "-o", "--output", type=Path, help="write output to this file"
    )
    parser.add_argument(
        "--chunk-bytes",
        type=int,
        default=1536,
        help="bytes per raw stream chunk, default: 1536",
    )
    parser.add_argument(
        "--skip-chunk-bytes",
        type=int,
        default=12,
        help="non-stream bytes to skip at the start of each chunk, default: 12",
    )
    parser.add_argument(
        "--keep-blank-lines",
        action="store_true",
        help="preserve repeated newline controls",
    )
    parser.add_argument(
        "--show-controls",
        action="store_true",
        help="render stream controls as <ooo>",
    )
    args = parser.parse_args(argv)

    text = decode_stream(args.raw_file.read_bytes(), args)
    if args.output:
        args.output.write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
