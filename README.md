# re-dimip

Reverse engineering of **ДИМИП (DIMIP)** — *Диалоговый Монитор Индивидуального
Пользования*, the interactive text-editing monitor for the BESM-6 under OS DISPAK.

Попытка дизассемблирования двоичного кода монитора ДИМИП для БЭСМ-6.

Only the working binary survives; this project disassembles and documents it, following
the [re-dispak](https://github.com/leobru/re-dispak) methodology.

## Contents

| File | Description |
|------|-------------|
| `dimip.bin` | Monitor image: 2048 words, loaded at octal `02000` |
| `dimip.b6` | DISPAK job deck that bootstraps the monitor |
| `dimip.sym` | Symbol table |
| `disasm.sh` | Reproducible disassembly recipe (generates `dimip.lst`) |
| `trace` | Reference simulator execution trace (initialization path) |
| [`DIMIP-analysis.md`](DIMIP-analysis.md) | First-pass structural analysis — start here |

## Reproducing the listing

```sh
./disasm.sh > dimip.lst
```

Uses [`disbesm6`](https://github.com/leobru/dispak-tools) (override its location with the
`DISBESM6` environment variable). The script feeds every trace-executed address as an entry
point so that routines reached only through the directive dispatcher decode as code.
