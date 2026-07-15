# DIMIP monitor — first-pass structural analysis

*Reverse engineering of `dimip.bin`. Companion artifacts: `dimip.lst` (annotated
disassembly), `dimip.sym` (symbol table), `disasm.sh` (reproducible recipe).*

## 1. What DIMIP is

**ДИМИП** — *Диалоговый Монитор Индивидуального Пользования* ("interactive monitor
for individual use") — is an interactive, terminal-driven text editor / file monitor
for the BESM-6 running under OS **ДИСПАК (DISPAK)**. (User manual:
`besm6.github.io/wiki/DIMIP-manual.md`.) It lets a user edit text files on tape/disk
(МЛ/МД), organises files into per-user **archives** (архив) addressed through a
**catalog** (каталог) keyed by **идпол** (user id) + **ключ/пароль** (key/password),
runs **subordinate tasks** (ПЗ) under monitor control, and provides a macro processor.
The resident monitor occupies 2 zones on МЛ/МД and needs 5 pages of core.

This matches the binary exactly: the data segment holds the prompt/error strings
`КЛЮЧАР`, `ПАРОЛЬ`, `ИДПОЛ`, `БЮДЖ`, `ФАЙЛ`, `ЗОНА`, `БИБЛ`, `СТРОКИ ФАЙЛА`, `ДЛИ.ТФ`,
`ЕКОНЕЦ`, `ЧУЖОЙ`, `КЛЮЧ`, and the code is built around terminal I/O (Э71), disk/tape
exchange (Э70), an asynchronous event loop (Э53), and subordinate-task control.

## 2. Provenance & how to reproduce

| File | Role |
|------|------|
| `dimip.bin` | 12288 bytes = **2048 BESM-6 48-bit words** (octal 04000), load address **02000**. |
| `dimip.b6`  | DISPAK job deck: loads at 6000, runs `Э70 6000`, transfers control to **02000** (`к 00 30 02000`). |
| `trace`     | 947-line simulator execution trace of the deck (startup path only — see §6). |
| `dimip.lst` | Annotated disassembly, produced by `disasm.sh`. |
| `dimip.sym` | Seed symbol table (`<octal-addr> <type> <name>`; type B/C=code, D=data, G=GOST text, A=addr). |

Regenerate the listing:

```sh
./disasm.sh > dimip.lst      # = disbesm6 -b -a2000 -e2000 <trace-entries> -n dimip.sym dimip.bin
```

`disbesm6` (`/home/leob/git/leobru/dispak-tools/disbesm6`) does flow analysis but cannot
follow the computed jumps of the directive dispatcher, so `disasm.sh` additionally feeds
**every address the trace executed** as an entry point (`-e`). With those, every
trace-reached instruction decodes as code (verified: 0 trace addresses left as data).

## 3. Memory layout

```
02000 ┌───────────────────────────── entry / initialization (СТАРТ, §4)
      │  02000–02073  startup code
      │  02074–02530  data: dispatch/keyword tables, message strings, constants
      │  02502–...    interleaved code + data (directive handlers, helpers)
      │  03141 ГЛЦИКЛ main monitor loop;  03331 ЖДИКОМ terminal read/wait
      │  03xxx–04xxx  directive handlers, field pack/unpack helpers, macro engine
      │  05xxx        more handlers
05741 │  05741–05777  resident constants (masks, addresses; D057xx)
05777 └─────────────────────────────
```

Code and data are interleaved (typical of hand-written BEMSH). Working variables live
**below** 02000 in resident low core (rendered as literals `'1774'`, `'1350'`, … in the
listing) — they are *not* part of `dimip.bin` and so are not yet named.

## 4. Startup / initialization (`02000`–`02073`)

Entered at **02000** after the deck's bootstrap. The sequence (left/right instruction
pairs per word; see `dimip.lst`):

| Addr | Action |
|------|--------|
| 02000–02001 | Build an Э70 info word (`D05773`+`D02074`); `Э70 70000` — initial disk exchange (load working zones). |
| 02005 | `Э50 103` — set **abort-reaction program address**. |
| 02006 | `Э50 102` — set **number of intercepted aborts**. |
| 02007 | `Э63 3` — **reserve CPU time for abort processing** (info `D02505`). |
| 02010 | `Э50 114` — request **date & machine number**. |
| 02011–02016 | Build flag/mask words (`'1731'`, `'1732'`…) from constants `D02164/D02346/D02347/D02350/ENDMRK`. |
| 02017 | `Э53 21` — **declare/clear events** (init the event scale). |
| 02020 | `Э53 11` — set **event-decoder (дешифратор) address**. |
| 02021 | `Э53 12` — set **event-scale mask** (`D05771`). |
| 02022–02024 | Loop: copy 19-word working table `06100..06123` into low core `01741..01764`. |
| 02025 | `Э50 100` — request **job cipher (шифр)**. |
| 02026 | `Э71 D02504` — first **terminal I/O**; `нед D05742` status check. |
| 02030 | `пв G05216` — call setup subroutine. |
| 02032–02035 | If `ОПКАТ` is nonzero, `Э70 ОПКАТ` reads the saved catalog/monitor setup zone and `пв G03335` formats the selected header word. |
| 02040 | `Э67 D02400` — install **debug/abort handler**; info word `D02400 = A(ГЛЦИКЛ)` → after any abort, resume the main loop. |
| 02041–02046 | Final table setup; calls `G02070`, `G03402`, `G02064`. |

In short, init = **fault/abort handling** (Э50 102/103, Э63 3, Э67) + **system info**
(Э50 100/114) + **asynchronous event mechanism** (Э53 21/11/12) + **load monitor zones**
(Э70) + **open terminal** (Э71), then fall through into the monitor proper.

`setup.b6` covers the `02032` path by placing the desired catalog state in the `06100`
copy-down table. The copy loop at `02023` transfers `06100..06102` to `01741..01743`, so
startup sees:

| source | destination | value | meaning |
|--------|-------------|-------|---------|
| `06100` | `ОПКАТ`   | `0010030000550000` | read LUN 55 zone 0 into `БУФЕР` |
| `06101` | `ОПКАТ+1` | `0000010000000000` | user-table index 1 (`БУФЕР+30`) |
| `06102` | `ОПКАТ+2` | `0000000100401404` | selected catalog/volume marker `001234` |

With `лен 55(1234)`, this reads volume 1234 through LUN 55, formats the selected user-table
word `БУФЕР+30` (`КОС`) into `D02334`, loads `ПАДМ` from `БУФЕР+3`, and enters the main loop
as an already selected library.

## 5. Extracode (system-call) usage

All confirmed against `extracodes.txt`. АИСП = executive address (subfunction selector).

| Extracode | Used as | Meaning (extracodes.txt) | Role in DIMIP |
|-----------|---------|--------------------------|---------------|
| **Э50** | 100 | запрос шифра задачи | get job cipher |
| | 102 | установка числа перехватываемых авостов | set intercepted-abort count |
| | 103 | установка адреса программы реакции на авост | set abort handler addr |
| | 114 | запрос даты и номера ЭВМ | get date / machine № |
| | 131 | дозаказ набора данных | request extra dataset |
| **Э53** | 11 | установка адреса дешифратора событий | install event decoder |
| | 12 | установка маски шкалы событий | set event mask |
| | 17 | закрытие задачи до наступления событий | **suspend until event** (idle wait) |
| | 21 | объявление/гашение событий | declare/clear events |
| **Э62** | 44 | отказ от выходного потока | release print output stream |
| | 30000–67777 | сдвиг по НД / отказ от НД | position / release dataset |
| **Э63** | 3 | резервирование времени на обработку авоста | reserve abort-handling time |
| | (СМ=`КЛЮЧАР`) | создание/каталог/доступ к области, бюджет | archive/area access control (see §8) |
| **Э66** | — | обращение к стандартным программам | call library subprograms |
| **Э67** | D02400 | управление базовыми средствами отладки | install abort/break handler → ГЛЦИКЛ |
| **Э70** | (info words) | обмен ОП ↔ внешняя память (МБ/НД/МЛ) | **disk/tape exchange**: archive zones, temp area, monitor zones |
| **Э71** | (info words) | обмен с терминалом | **terminal I/O**: read directives, write prompts/messages |

The combination **Э53 11/12/21 + Э53 17 + Э71** is the heart of the interactive monitor:
install an event decoder and mask, then loop issuing terminal I/O and *suspending until an
event* (terminal-ready / subordinate-task signal) rather than busy-waiting.

## 6. Control flow — what the trace shows

The reference `trace` exercises **only initialization**: the DISPAK resident
extracode-070 path (`00010`→`03651`…), the deck bootstrap (`06001`), then DIMIP startup
`02000`–`02073` and the subroutines it calls (`02070, 03041, 03323, 03331, 03335, 03507,
05216`, ranges `03141–03251, 03474–03551, 03736–03776`). It ends as the monitor settles
into its event-wait. **No interactive directive is driven**, so the directive handlers
(§8) are reached only via the dispatcher and must be read statically.

Two pivotal routines, both well-supported by evidence:

- **`ГЛЦИКЛ` (03141)** — main monitor loop. It is the target installed as the Э67
  abort/restart handler (`D02400 = A(ГЛЦИКЛ)`) and the most common jump/return target in
  the code; it issues `Э62` dataset positioning and dispatches work.
- **`ЖДИКОМ` (03331)** — terminal read / wait: `Э71` terminal exchange immediately
  followed by `Э53 17` (suspend until event) = "issue prompt, await the user's directive".

## 7. Data & message strings

The prompt/error fragments are assembled from text constants around `02345`–`02366`,
`02456`, `02506`–`02507` (named in `dimip.sym`): `КЛЮЧАР, СТРОКИ, ФАЙЛА, БИБЛ, ЗОН(А),
ПАРОЛЬ, ИДПОЛ, БЮДЖ, ФАЙЛ, ДЛИ.ТФ, ЕКОНЕЦ, ЧУЖОЙ, КЛЮЧ`. These correspond directly to the
catalog-setup directive `КТ <ТОМ> <ЗОНА> <ИДПОЛ> <КЛЮЧ>` and access errors in the manual.

A keyword-like table sits at `02176`–`02226` (`SUВАR, INFВU, МULСV, …, IЕQУ=` — partially
mangled by text-encoding guesses) and an address/parameter table at `02237`–`02325`
(several entries auto-decode as `конк A(Gxxxx)`, e.g. `A(G02536)`, `A(G03135)`,
`A(ГЛЦИКЛ)`). Together these look like the **directive keyword → handler dispatch table**
that drives the parser — the prime target for the next pass.

## 8. Directive dispatch & data structures

- **Directive dispatcher — decoded** (see §8a below).
- **Archive / catalog** — DIMIP keeps its archive in disk zones with a catalog
  (идпол/пароль/file map) in the first zone, accessed via `Э70`. Numeric volumes use the
  disk attach path (`Э50 131`, §8e). Named `<ТОМ>` values use the OS-level
  **`Э63`/`КЛЮЧАР`** path in `ДИРКТ`: `05251 сч КЛЮЧАР; Э63 ОПКАТ+4`, with the parsed name
  in the surrounding `ОПКАТ` cells. This is the ARFA/named-area access path.
- **Temp area / output buffer** — the editing scratch zones (временная область) and the
  subordinate-task output buffer (буфер вывода) named in the manual; their disk addresses
  appear among the `D057xx` constants and the Э70 info words.
- **Field pack/unpack helpers** — routines `G03041/G03050/G03052`, `G04102/G04112/G04121`
  use multiply-by-constant + `счмр` (`D02415/D02417/D02420/D02421`) to extract/insert
  bit-fields of catalog/zone-address words.

## 8a. The directive dispatcher (decoded)

Parsing/dispatch is done by **`РАЗБОР` (03207)**: it copies the parsed command line into a
work buffer (`'1345'`…), packs the directive name into token `'1347'`, and runs the scan
loop **`G03222`**. Each table entry is loaded, right-shifted by 24 (`СДА 64+24`) to expose
its key, and XOR-compared with `'1347'`; on a match, **`G03236`** pulls the handler address
out of the entry's low 15 bits into `М13`, inspects the flag bits, and jumps to the handler.

**Dispatch table — `ТАБДИР` (02274–02325, 26 entries).** Each 48-bit entry is:

```
 bits 48..25 (24)        bits 24..16             bits 15..1
 ┌────────────────────┬──────────────────┬───────────────────┐
 │ key: 3 GOST chars  │ flag bits        │ handler address   │
 │ (directive name)   │ (pre-handler     │ (jumped to via    │
 │                    │  actions)        │  М13)             │
 └────────────────────┴──────────────────┴───────────────────┘
```

Decoded keys → handlers (regenerate with `./decode_dispatch.py`; named in `dimip.sym`):

| Key | Handler | Key | Handler | Key | Handler |
|-----|---------|-----|---------|-----|---------|
| `КТ`  | `ДИРКТ`  05232 | `ПЕЧ` | `ДИРПЕЧ` 04703 | `Л` | `ДИРЛ` 05603 |
| `К`   | `ДИРК`   05520 | `ИНФ` | `ДИРИНФ` 05026 | `В` | `ДИРВ` 05717 |
| `ПЕР` | `ДИРПЕР` 05014 | `ЗАМ` | `ДИРЗАМ` 05222 | `Н` | `ДИРН` 05600 |
| `ПОЛ` | `ДИРПОЛ` 05317 | `РЕД` | `ДИРРЕД` 05644 | `И` | `ДИРИ` 03063 |
| `ВЫЙ` | `ДИРВЫЙ` 03523 | `ВЫБ` | `ДИРВЫБ` 05173 | `З` | `ДИРЗ` 05667 |
| `ВОЙ` | `ДИРВОЙ` 05176 | `СФ`  | `ДИРСФ`  05361 | `С` | `ДИРС` 03341 |
| `ПП`  | `ДИРПП`  05157 | `ЗП`  | `ДИРЗП`  05142 | `П` | `ДИРП` 03364 |
| `А`   | `ДИРА`   05134 | `О`   | `ДИРО`   03135 | `Б` | `ДИРБ` 05051 |
| `Ф`   | `ДИРФ`   03404 | `Д`   | `ДИРД`   05727 |     |              |

The **flag bits** (bits 16–24) gate pre-handler behavior in `G03236` (e.g. `ПЕР/ПЕЧ/Ф`=140,
`И/З`=120, `Л/В`=100, `ПОЛ`=400); their exact meanings are only partially decoded.

The scan walks an **`М7`-indexed window** of the table whose start depends on the monitor
state, i.e. which directives are valid in the current mode:

- **`КТ?` / general mode:** `М7` starts at `-18`, so the scan covers `02303`–`02324`
  (`К, КТ, ИНФ, ЗАМ, РЕД, ПЕЧ, …`). The single-letter entries below `02303` are not visible.
- **Editor mode** (entered by `РЕД`): `М7` starts at `-25`, so the scan now begins at
  `02274` — exactly where the **single-letter editor commands** `Л В Н И З С П` live, which
  is why they only work after a file is opened. Code at `05732`–`05740` reads/writes
  `ТАБДИР`, consistent with this mode switching.

**Validated dynamically** (`cat input.txt | dispak -t -t dimip.b6`):

- `КТ 2053 1 TEST KEY` → scan `G03222` matches at `02317` (compare shows `acc=025062` =
  `КТ` GOST-packed = that entry's `hi24`) and reaches **`ДИРКТ` (05232)**.
- `РЕД 2048 *0000` → **`ДИРРЕД` (05644)**; then the editor command `Л` → **`ДИРЛ` (05603)**,
  with the scan now starting at `02274` (`М7=-25`). End-to-end confirmation of both the entry
  format and the mode-dependent window.

## 8b. In-memory file representation & the `Л` (Листинг) directive

### File representation

A file is a sequence of **numbered lines** (manual §6.2.1: *"Файл — набор строк символов"*).
The full file lives in the **временная область** — zones on МД (≤ 64 tracts) — and a working
window is paged into core via `Э70`. The memory map while editing:

```
00000–01777  resident OS + DIMIP working variables ('13xx','17xx' cells)
02000–05777  DIMIP monitor (code + data, the "2 zones")
06000 …      file editing window — up to 5 листов (the "5 листов ОЗУ"),
             lines stored contiguously; rest of the file stays on МД (Э70-paged)
```

Lines are stored **contiguously and length-prefixed**, starting at **06000** (the base kept
in `М1`, = `D05773+5`). Each line is:

```
 header word:  bits 48..25  auxiliary/flag field (low bits gate special handling in G05621;
                            bits 30..25 = field count, consumed by symbolic <RЕА — §8l)
               bits 24..7   line NUMBER (18 bits)
               bits  6..1   LENGTH L = total words in the line, incl. header
 + (L-1) words of text in **ГОСТ 10859**, one char per 8-bit byte (digits 000-011,
   '.' = 016, А-Я at 040-076, Latin D F G I … from 077), SIX chars per word; a 0o377
   byte ends the text (МКП channel reads detect the last word via МСКМАР — §8l)
```

Because the number is stored *in each line*, numbering can be non-monotonic and even
duplicated (manual §6.2.4) — operations address lines by this stored number, not by position.

The central accessor is **`ЧИТСТР` (03067)** (called from 9 sites): it reads the header at
`М1`, masks the low 6 bits (`и D02426`=`&077`) to get L, copies the whole line into the
current-line buffer at **'1746'**, then **advances `М1` by L** to the next line and bumps a
line counter (`М11`). Walking the file is just repeated `ЧИТСТР`. The line number is unpacked
for display by `G03031` (`asn 106; aax 2422` = `(header>>6) & 0777777` → cell `'1774'`).

### The `Л` directive (manual §6.2.5)

`[$]Л [<N1> [<N2> [<ОБРАЗ>]]]` — **Листинг**: print lines from the temp area to the terminal.
No args = sequential listing; `N1` = just that line; `N1 N2` = the range; a 3rd `<ОБРАЗ>` =
only lines in the range matching the pattern; the `$` prefix suppresses the printed numbers.

Handler **`ДИРЛ` (05603)**: `пио G05616(М12)` splits the no-arg path (`М12=0`) from the
arg-driven path. The argument count/values come from the parser (`'1347'` token, numeric
args via `G04121/G03041`). The listing loop fetches each line with `ЧИТСТР`, converts the
line number to decimal (`G03014`/`G03031`, dividing by the constants `D02416/D02417`), and
writes number+text to the terminal via `Э71`.

**Validated dynamically:** in the `РЕД 2048 *0000` / `Л` trace, `ЧИТСТР` reads the header
`…0112` at 06000 → L=`012`=10 words, line number = 1 (→ `'1774'`), copies the 10 words to
`'1746'…'1757'`, advances `М1`, and proceeds to format/emit the line.

### `Л` patterns, `Н`, and the `З` substitute form — traced (`listing.txt`)

The `listing.txt` coverage session exercises the pattern forms of the listing/edit
directives (429 words on its own; `dimip.uncov` 291→256). Handlers: `ДИРН` `05600`,
`ДИРЛ` `05603`, `ДИРЗ` `05667`.

- **`Л <Н1> <Н2> <ОБРАЗ>`** works as documented — substring match over the range, `$`
  suppresses numbers, no matches → «НЕТ ТЕКСТА». (composite.txt's `л 10 50 строчка` never
  exercised the matcher because its range was empty — the file's lines were numbered 1–5.)
- **The manual's `?` wildcard does not exist in this build.** A typed `?` arrives as ГОСТ
  `|` (`0o130`, via the КОИ7 input table), and the `Л`/`Н` match loop (`G05611`) has no
  wildcard check — `уз?р` is a literal and matches nothing.
- **`Н <ОБР>`** finds by substring across the whole file; multi-word patterns (with
  spaces) work; `$Н` lists all matches unnumbered.
- **`З <N1> <N2> <ОБР> <ЗАМ>` — the substitute form is space-delimited, NOT the manual's
  `<R><ОБР><R><ЗАМ><R>`.** Mechanism (`05671`–`05710`): the directive dispatcher leaves
  the byte at the parse position in `КОМАНД`, which `ДИРЗ` uses as the first-char fast
  reject (`нтж КОМАНД`, `05671`) — with `/узор/…` that byte is the `/` itself, so lines
  are scanned for `/` and nothing ever matches (trace-verified: `КОМАНД` = `0o14`). The
  ОБР body is walked via the `АРГ3+24` pointer and **terminates on a ГОСТ space**
  (`нтж МСК4`, `05675`); the replacement (`АРГ3+25`) is spliced in at `G05701`–`05710`
  and the line rebuilt through `LNINS` (`05711`). All occurrences in the range are
  replaced, shorter/longer replacements included (verified: `УЗОР→УЗЕЛ`, `УЗЫР→ТРИ`,
  `УЗОР→РАЗУЗОР`, two occurrences on one line). No occurrences → «НЕТ ТЕКСТА». A bare
  `З N1 [N2]` (no pattern, `М12=0`) deletes the range and enters input mode, and a glued
  `з N1 N2/…/…/` suffix parses as that no-pattern form — beware in scripts.
- **`≠` paging**: the screen-full pause (`G03530`, `03532`–`03537`) continues on a blank
  line; a **non-blank** line *aborts the listing and is consumed* — it is not re-executed
  as a directive.

Still uncovered in this area: `05623`–`05627` — `G05621`'s print path for a line whose
header carries a nonzero **field count** (bits 25–30, the same field symbolic `<RЕА`
reads, §8l); no tested flow creates such lines yet.

### `$ПЕЧ` formatted hardcopy output — traced (`bilist.txt`)

`bilist.txt` enters `РЕД`, loads a long manual fragment into the temporary area, and runs
`$ПЕЧ`. Against the current coverage set, `bilist.cov` contributes 31 unique half-word
locations inside `ДИРПЕЧ`: `04714`–`04721`, the residual-line countdown at
`04747`/`04750`, the marked-byte path `04761`–`04763`, `04773`, and `05003`–`05006`.

The output is not a terminal `Л` listing. It is a formatted АЦПУ page: `bilist.out` shows a
form feed, two page/column numbers, and two text columns. The covered code does the
corresponding page-layout work:

- `04714`–`04721` emits a deferred/second-column page image. It sets the print-buffer cursor
  to `070036`, loops over 59 rows, copies 10-word row chunks with `G05007`, pads the
  `070024` area with blanks, and finally sends the page through `Э64 D02372`.
- `04773` is the alternate return from the line-filling loop at `G04755`: when the row
  advance/test at `04772` does not return directly to the caller, it forces `М11=1` before
  returning, so the formatter continues with the next page/column state.
- `04761`–`04763` is the special line-fill path for a packed byte that trips
  `(word + D05746) & МСКМАР`; `D05746` is bytewise `003`, so an input `\\` converted to
  GOST `0175` is enough to set the `0200` marker bit and exercise this path.
- `05003`–`05004` is the `$ПЕЧ` next-page control path reached from `G05000`. It recognizes
  the `..` control sequence checked against `ТЧКТЧК`, sets `М13=1`, and tests the remainder
  in `РАБ` with `ржа '13'`. A `..NN` line continues through `05005`–`05006`, shifts the
  numeric remainder, sets the return state for `G04747`, and parses the count with `G03011`.

## 8c. The catalog / archive on-disk format & the `СФ` directive

A user logs in and lists the catalog like this (terminate with `ВЫЙ`; the `≠` continuation
prompt pages long output, so feed blank lines to continue):

```
КТ 2148 .1640     set catalog: volume 2148, catalog in zone 01640 → prompt "ВОЙДИ"
ВОЙ ПРОГОН        log into library (идпол) ПРОГОН → banner "*ДИМИП-МКП 05.04.85*"
СФ                show the file catalog
ВЫЙ               leave
```

### `СФ` handler (`ДИРСФ`, 05361)

`Э70 D02412` reads the catalog zone into core; the column header is copied from the template
at `СФАЙЛ` (02363: `ФАЙЛ ЗОНА ДЛИ.ТФ .БИБЛ.`) and emitted; then the file-directory entries are
walked (formatter at `G05452`, runs once per file), each formatted as
`name · zone · length · encoding · идпол` and written to the terminal via `Э71`.

### On-disk catalog (zone 01640 on volume 2148; dump with `besmtool dump 2148 --start=01640 --length=1`)

The catalog zone holds: control words (0–5), a free/occupied **tract bitmap** (≈6–17), the
**идпол records** (e.g. word 35–36 = signature `*ДИМИП` + library name `ПРОГОН`), and the
**file directory** — an array of **2-word entries**:

```
 word 1:  file NAME — 6 GOST characters, right-justified (e.g. ТРАК, ПАМЯТЬ, ДИМИП)
 word 2:  metadata (besmtool's four 12-bit groups, high→low):
            bits 48-45  type nibble — four independent FLAG bits (see "The type field
                        decoded" below):  48 = created-but-never-written (the dot) ·
                        47 = I (ISO text) · 46 = К (binary) · 45 = Б (never set by
                        dimip.bin) · all clear = У (ГОСТ text)
            bit  40     macro entry — displays as type М (Е40)
            bit  38     З, encrypted (МШИФР)
            bits 36-25  0100       constant ("entry present")
            bits 24-13  length × 8 (number of tracts = field >> 3)
            bits 12-1   start zone, RELATIVE to the archive base
```

The displayed absolute zone = **archive_base + relative_zone**, where the archive base is the
catalog zone + 1 (here 01641). Storing zones relatively is exactly what the manual promises:
*"в каталоге записываются относительные положения файлов … старый архив может быть переписан
на другой том"* (the archive is volume-relocatable). Worked examples, all confirmed against
the live `СФ` output:

| File | name word | metadata | enc | length | rel | abs zone |
|------|-----------|----------|-----|--------|-----|----------|
| `ТРАК`   | `…3230202a` | `0000 0100 0010 0055` | У | 1 | 055 | 01716 |
| `ПАМЯТЬ` | `2f202c3e323b` | `2000 0100 0030 0041` | I | 3 | 041 | 01702 |
| `ДИМИП`  | `…2428 2c282f` | `1000 0100 0020 0001` | К | 2 | 001 | 01642 |
| `КЗ2`    | `…2a2702` | `2000 0100 0060 0005` | I | 6 | 005 | 01646 |
| `КЗ5`    | `…2a2705` | `0000 0100 0120 0016` | У | 012 | 016 | 01657 |

(The `У/I/К` column is each file's stored **type**: `У` = ГОСТ text, `I` = ISO text,
`К` = **binary**. Login and the `$` prefix are covered in §8d.)

### The type field decoded — У / Б / К / М / I and the dot (static, byte-exhaustive)

**Display** (`ДИРСФ` per-entry formatter, `05434`–`05457`): the type nibble = **bits 45–48**
of metadata word 2 (`сда 64+44` → `М16` at `05445`); if bit 40 (`Е40`, `02432`) is set the
index is forced to 3 (`05446`–`05447`) — that is how macro entries display as `М`. The
two-character type string is then fetched from **`D02143+2(М16)`** (`05450`): the strings
piggyback on the **м32 fields of the ГОСТ→КОИ-7 conversion-table rows** (the table at
`02075`+, indexed by ГОСТ code; same dual-use-table trick
as the МКП command keys), rows `02145`–`02163`:

| nibble | string | row | | nibble | string | row |
|:--:|:--:|:--:|---|:--:|:--:|:--:|
| 0 | `У ` | `02145` (И) | | 8 | `У.` | `02155` (Р) |
| 1 | `Б ` | `02146` (Й) | | 9 | `Б.` | `02156` (С) |
| 2 | `К ` | `02147` (К) | | 12 | `I.` | `02161` (Ф) |
| 3 | `М ` | `02150` (Л) | | 14 | `..` | `02163` (Ц) |
| 4 | `I ` | `02151` (М) | | | | |

So the nibble is four independent flag bits, and each bit is proven by its writer:

- **bit 48 = "created, never yet opened for write" — the dot.** `СФ`-create stores it
  (below); the file-open paths **toggle** it with `нтж Е48` (`Е48` = `02431`): the common
  open at `G02666` (`02666`–`02667`) and МКП `ОРЕ` (`КОМОРЕ`, toggle at `04060`), which calls
  `ЗАПКАТ` only when the toggle *clears* the bit — i.e. the first open of a fresh file
  permanently drops the dot on disk (`У.`→`У `, `I.`→`I `). `G02666` also saves the
  pre-toggle **bit 47** as the ISO flag `ПРЕФ+2` (`сда 64-1; и Е48`, `02667`–`02670`),
  independently confirming bit 47 = I.
- **bit 47 = I, bit 46 = К, none = У.** `СФ <ИМЯФ> <КЗОН> [У|I|К]`-create (`05374`–`05406`):
  the type letter in `АРГ3` is matched (low byte, `МСК8`) against words `02257`–`02262` —
  low bytes `000` (no letter) / `063` (`У`) / `102` (Latin `I`) / `052` (`К`) — the
  ГОСТ 10859 codes — and the stored nibble is the low 4 bits of the parallel table `02264`–`02267`
  (`сч D02262+2(М7); сда 64-44` at `05403`): default → **8** (`У.`), `У` → **8**, `I` → **12**
  (`I.`), `К` → **2** (`К `, no dot — К zones are written by `Э70` from лист 3, not through
  open/write). Matches the live examples above: ТРАК `0000`=У, ДИМИП `1000`=bit 46=К,
  ПАМЯТЬ `2000`=bit 47=I.
- **bit 40 = macro (`Е40`), not part of the nibble.** The `$К` macro-library writer
  (`05550`–`05561`) builds each macro's catalog entry with `или Е40` (`05552`); display
  forces `М ` as above. (Manual §6.2.7.23: macro names appear in `СФ` with type `М`.)
- **bit 38 = З (encrypted).** At create, `МШИФР` (`02433` = bit 38) is ORed into word 2 iff
  the `З` argument is present (`05404`–`05406`).

**Type `Б` is unreachable from dimip.bin.** `Б` is bit 45 (nibble 1, or 9 dotted), and no
code path sets it: there is no bit-45 constant in the image (only `Е40`/`Е48`/`МШИФР`), and
an enumeration of *every* store to a catalog entry word — create (`05403`–`05406`), the
macro writer (`05550`–`05561`), the two `Е48` open-toggles (`02666`, `04060`), rename
`ДИРЗАМ` (`05222`, name word only), delete `ОСВЗОН` (`05345`, clears the entry), catalog
init in `ДИРКТ` (zone wipe at `05271`) — writes only nibbles 8/12/2, `Е40`, or toggles
bit 48. So nibbles 1, 9 and 14 (`Б `, `Б.`, `..`) are **display-only** in this build: they
can appear in `СФ` output only if the bit arrives from outside — another program/build
writing the `*ДИМИП` archive format, or a hand-edited catalog zone. The paired `Б `/`Б.`
strings do show the format *reserved* Б as a first-class type with the same
created→written lifecycle as У and I.

## 8d. Login path and the `$` prefix

### Login: `КТ` → `ВОЙ`

- **`КТ <том> .<зона>`** (`ДИРКТ`, 05232) sets the catalog location (volume + zone) and reads
  the catalog zone; the monitor then prompts **`ВОЙДИ`** ("log in").
- **`ВОЙ <идпол>`** (`ДИРВОЙ`, 05176) logs into a library: it takes the идпол name (parser
  tokens `'1351'`/`'1352'`), looks it up among the catalog's идпол records and makes it the
  current library, reads that library's file directory into core (via `G05216`), and prints
  the banner **`*ДИМИП-МКП 05.04.85*`** (inline text at `D05212`, emitted by the `G02064`
  inline-argument printer). Control then returns to general mode (`СФ`, `РЕД`, …).

### The `$` prefix

`$` is the input character code **`0127`**, recognized only as the **first** character of a
directive line. The line lexer marks token boundaries with a high bit per word (mask
`МСКМАР`=`D02445`); routine **`МЕТКИ`** (03540) scans those markers, and `03157`–`03160` then
sets the **prefix flag cell `'1707'`** to `ФЛАГД` (`D02434` = `0100000000`) when the leading
char is `$`. The `$` is skipped, so the directive-name token (`'1347'`) is built from the
remainder and is *identical* to the unprefixed form — verified dynamically: both `СФ` and
`$СФ` pack to `030464`.

The same parse step latches the indicator into **register `М3`** as well as the flag cell:
at `03153`–`03154` the first line char is XOR-compared with the `$` code (`нтж D02076`) and the
result is loaded into `М3` (`уи М3`), so **`М3 == 0` ⟺ the line began with `$`** — that is the
very test (`пино G03161(М3)` at `03157`) that decides whether `'1707'` gets `ФЛАГД`. `М3`
survives dispatch into the handler. So a handler can consult the prefix in **either** form:
- via the **flag cell `'1707'`** — e.g. `ДИРСФ` ORs `'1707'` with the file-name argument at
  `05366` to take delete (`$СФ <ИМЯФ>`) vs. show (`СФ`);
- via **`М3`** — e.g. `ДИРПОЛ` has no `'1707'` test at all; at `ПОИСКП` (`05322`) it does
  `пио ИСКЛП(М3)`, so `$ПОЛ` (`М3=0`) branches to `ИСКЛП` (`05340`), which clears the идпол
  record and frees its library's zones in the catalog map, vs. the plain search/insert path.

Behavior table:

| directive | plain | with `$` |
|-----------|-------|----------|
| `СФ` | show the catalog | `$СФ <ИМЯФ>` — **delete** file `<ИМЯФ>` |
| `Л`  | list lines **with** numbers | `$Л` — list **without** numbers |
| `ВЫЙ`| leave | `$ВЫЙ` — leave **and print the session protocol** to the printer |
| `А`  | toggle protocol mode | `$А` — discard the accumulated protocol |

`ДИРВЫЙ` (03523) shows the mechanism concretely: on the protocol-dump path it issues
`Э62 44` (release the output/print stream). So `$` does not change *which* handler runs — it
changes *what that handler does*, sometimes drastically (e.g. `СФ` show → `$СФ` delete).

## 8e. Catalog creation — administrator path (`$КТ` / `ПОЛ` / `ВОЙ`), traced

Driven on scratch volume **1234** with the input
`$КТ 1234 0000 0100` / `ПОЛ ПРИМЕР` / `ВОЙ ПРИМЕР` / `ВЫЙ`
(`cat input | dispak -t -t dimip.b6`). The dialogue confirms the whole flow:

```
УС.КТ                 <- startup prompt (set catalog)      ;  reply: $КТ 1234 0000 0100
ВОЙДИ                 <- catalog created, log in           ;  reply: ПОЛ ПРИМЕР
ВОЙДИ                 <- user added, log in                ;  reply: ВОЙ ПРИМЕР
*ДИМИП-МКП 05.04.85*  <- login banner (ПРИМЕР accepted)    ;  reply: ВЫЙ  -> clean exit
```

### How a user volume becomes addressable — `Э50 131` (attach volume to LUN)
DIMIP does **not** reach the user's volume through a deck `ЛЕН` line. It attaches it at
run time: the dispak handler `Э50 131` (extra.c `case 0131`, *"attach volume to handle"*)
takes the LUN in `acc.l>>18` and the **BCD** volume number in `acc.r`. Routine
**`ПОДКАТ`** (`G03656`/`G03660`) builds that word from `АРГ1` (the typed `<ТОМ>`):

```
Э50 131 , acc = 6777 0000 0001 1064   ->  LUN = 067 ,  vol = NDISK(0o11064)=1234
```

Note `0o11064 == 0x1234` — the four typed digits as BCD nibbles. So `<ТОМ>=1234`
attaches **volume 1234 to LUN 67** (the catalog working LUN). The `..77..` middle field is
the mandatory `077` marker `Э50 131` checks.

Named `<ТОМ>` values are handled by `ДИРКТ`'s area-access branch: it parses the name into
the `ОПКАТ` work cells and calls `05251 сч КЛЮЧАР; Э63 ОПКАТ+4`. In practice this is the
ARFA/named-area path, for example for a name such as `coverage`.

### `$КТ <ТОМ> <НЗОНА> <ДАРХ>` — create catalog (`ДИРКТ`, 05232)
1. `ОТКНД` (05216): `Э62 60777` — release any catalog LUN held from a previous `КТ`.
2. parse `АРГ1..3` = `<ТОМ>=1234`, `<НЗОНА>=0`, `<ДАРХ>=0100` (archive length, **64** zones, octal).
3. `ПОДКАТ` (`G03656`): `Э50 131` attaches volume 1234 to LUN 67; builds the zone-I/O
   descriptor in cell `'1556'`.
4. **read** catalog zone: `Э70 '1556'` = *read* LUN 67 zone 0 → memory page `06000`
   (control word `0010030001670000`).
5. build the empty catalog image in `06000`: `<ДАРХ>` at word `0002`, the free-tract
   **bitmap** at words `0005`–`0006` (all-free), zero everything else.
6. `ЗАПКАТ` (`G05334`) — write the catalog back **twice**:
   * `Э70 РАБ` (`'1774'`) = *write* LUN 67 zone 0 ← `06000`  → the real catalog on **volume 1234**;
   * `Э70 ИНФЗ` (`'2413'`) = *write* LUN 40 zone 0 ← `06000`  → a working copy in the deck's
     **scratch area** (`ЛЕН 40(2с)`, `С`=scratch, not persisted — which is why only
     volume 1234 changes on disk).
7. `ГЛЦИКЛ` prints `ВОЙДИ`.

Э70 control-word format (per dispak `ddio()`): the executive address points at a word read
as two half-instructions — left `op&010`=read-zone / else write, `addr&03700<<4`=memory page;
right `op&077`=LUN, `addr&07777`=zone. Decoder: `e70.py` (e.g. `./e70.py 0000030001670000`).

### `[$]ПОЛ <ИДПОЛ> ...` — register a user/library (`ДИРПОЛ`, 05317)
Same skeleton: `ПОДКАТ`→`Э50 131` (re-attach 1234 to LUN 67) → `Э70` read zone 0 → scan the
идпол list (`'6116'`-stride entries) for `АРГ1` (`ПРИМЕР`), insert it → fall into `ЗАПКАТ`
(write volume + scratch) → `ВОЙДИ`. The result on **volume 1234 zone 0** (verified with
`besmtool dump 1234 --start=00000 --length=1`):

| word | octal | meaning |
|------|-------|---------|
| `0002` | `…0100` | `<ДАРХ>` archive length = 64 zones |
| `0005` | `3777777777777777` | free-tract bitmap (all free) |
| `0006` | `7777740000000000` | bitmap (cont.) |
| `0035` | GOST `*ДИМИП` | catalog signature |
| `0036` | GOST `ПРИМЕР` | the registered library/идпол name |

(`*` = GOST `031`; `ПРИМЕР` = `057 060 050 054 045 060`.) With no `<КЛЮЧ>`/`<ПАДМ>` given,
no password is stored, so the later `ВОЙ` needs none.

### `ВОЙ ПРИМЕР` — log in (`ДИРВОЙ`, 05176)
No `Э50 131` and **no `Э70`** in this directive: it works off the in-core catalog left in
`06000` by the preceding `ПОЛ`, finds `ПРИМЕР`, and prints the banner via `ПЕЧСО`
(`G05211→02064`). Success = the `*ДИМИП-МКП 05.04.85*` line.

### `Д` / `$Д` — administrator editing of the directive table (`ДИРД`, 05727)

The administrator directive `Д <ДИРЕКТИВА> <ПАДМ>` edits the in-core `ТАБДИР` entry for a
command, after checking the administrator password in `ПАДМ`. Without `$`, it XORs the
closed-command bit (`D02371`, `40000000(8)`) in the table entry. `ДИСПАТ` then rejects a
closed directive by printing `ЗАКР.` instead of dispatching it.

With `$`, the same handler takes a third argument:
`$Д <ДИРЕКТИВА> <ПАДМ> <НОВКЛЮЧ>`. The branch at `05735` distinguishes this `$` form; the
covered instructions `05736`-`05737` clear the old 24-bit directive key and OR in
`АРГ3<<24`. Thus `$Д` renames a directive key while keeping the old handler address and
flags. The coverage test uses `$д инф адм ззз`, verifies that `ззз` reaches the former
`ИНФ` handler, then renames it back with `$д ззз адм инф`.

New symbols from this trace: `ПОДКАТ` (`03656`, attach catalog volume + build I/O descriptor),
`ЗАПКАТ` (`05334`, write catalog back to volume + scratch copy).

## 8f. The `/*` suffix on `РЕД`, traced

Compared `РЕД` ⏎ ⏎ `ВЫЙ` against `РЕД/*` ⏎ ⏎ `ВЫЙ`
(`cat in | dispak -t -t dimip.b6`). Manual §6.2.4: `РЕД/*` reads the **80-byte format
(МС Дубна)** — a different on-volume text encoding — and enters editor mode, with a
diagnostic → general mode if the volume's encoding doesn't match.

What the trace shows:
- **Lexing.** `/` is a token separator and `*` (code `031`) is a modifier. The directive
  token `КОМАНД` is unchanged (still `РЕД`), so both dispatch to the same handler `ДИРРЕД`
  (`05644`). The `*` is carried in the arg area — the raw line cell `'1322'` becomes
  `РЕД *` (vs `РЕД` ), and `АРГ3+26` (`'1404'`) = `031`. (Same pattern as the `$` prefix,
  but as a trailing modifier rather than a flag cell.)
- **Behaviour (no `<ИМЯФ>`).** With no filename the file is *new*, so nothing is read from a
  volume. The `ДИРРЕД`-onward instruction stream is **byte-identical** between the two runs,
  extracode usage is **identical**, and the terminal output is identical — i.e. `/*` is inert
  here. The `*` format flag is parsed and stored but never consumed, because the encoding
  choice only matters on the file-**read** path (`РЕД/* <ИМЯФ>` / `РЕД/* <ТОМ> * <ЗОНА>`).

So `/*` changes *how an existing file's bytes are decoded on read* (80-byte МС-Дубна format),
not the new-file/line-input path exercised here.

## 8g. Writing a file: the `К` directive and the У / I on-disk formats, traced

The `К` directive (editor mode, manual §6.2.5) ends editing and writes the temp-area file
back to a volume. The raw form is `К[/*] <ТОМ><ТФ><ЗОНА>`, where `<ТФ>` (file type) is the
literal `*` for the МС-Дубна / ISO encoding and **absent** for the default ГОСТ encoding.
Two sessions were traced (`cat in | dispak -t -t dimip.b6`), both starting from the cold
`УС.КТ` prompt:

```
РЕД               <- no filename: enter LINE-INPUT mode (numeric prompts 00001 00002 …, step 1)
СТРОКА ПЕРВАЯ     <- line 1
СТРОКА ВТОРАЯ     <- line 2
                  <- empty line: exit input mode -> editor mode (prompt '*')
К 1234 0000       (session U)  |  К 1234 *0001   (session I)
ВЫЙ
```

`РЕД` with no filename is accepted **even with no catalog set** and drops straight into
line-input mode; the terminal dialogue is byte-identical for both sessions.

### Common write machinery (`ДИРК` 05520 → `ПОДКАТ` 03656)
Both formats share the front end: `ДИРК` parses `<ТОМ>`/`<ЗОНА>`, `ПОДКАТ` issues
`Э50 131` to attach volume 1234 to **LUN 67** (`acc = 6777 0000 0001 1064`, `0o11064`=BCD
`1234`) and builds the zone-I/O descriptor in `'1556'`, using the two Э70 **control-word
templates**:

| cell | value | role |
|------|-------|------|
| `D02450` (`ЧТНД`) | `0010030001670000` | **read** zone → memory page `06000`, LUN 67 |
| `D02451` (`ЗПНД`) | `0000340000670000` | **write** zone ← memory page `070000`, LUN 67, zone += `<ЗОНА>` |

The target zone is `template + <ЗОНА>` (e.g. `К 1234 0002` → `0000340000670002`). The write
happens via `Э70 '1736'` reached from `03133`.

The working raw external write form for `К 1234 *0010` reaches the descriptor
`03133: Э70 ОПФАЙЛ (=0000340000670010)`. The traced `к 1234 *0010 адм` probe reaches
`G05722`, compares `АРГ3` with `ПАДМ`, reloads the saved `АРГ2`, and jumps into `G03621`.
With `*0010` in `АРГ2`, the descriptor carries read/type bits; the trace rolls through
`04642: Э70 ОПЗОН` across successive zones and exits via `ОШ.В ИНФ.СЛ.ЭКСТ`.

### The У vs I fork (gated by the `*` type flag)
`ПОДКАТ` (`03665`–`03671`) tests the `*` type flag — parsed into the **ПРЕФ area, cell
`'1711'` (ПРЕФ+2)**, exactly the trailing-modifier mechanism of §8f — and forks:

* **No `*` → У / native format** (short path, ~300 instrs). The temp area is written
  **verbatim in DIMIP's native line format**: each line = one header word (line number in
  bits 24-7, length `L` in the low 6 bits) followed by `L-1` words of **ГОСТ 10859 text,
  one char per 8-bit byte, 6 chars per word** (§8b); the file ends with the terminator
  `7777777777777700` (`D02453`). Confirmed by writing to zone 2
  (`besmtool dump 1234 --start=2 --length=1`):

  ```
  0002.0000  0047300000000104   header: line 1, L=4  (=1 header + 3 text words)
  0002.0001  1423106013425040   "СТРОКА" = ГОСТ bytes 061 062 060 056 052 040
  0002.0004  0047300000000204   header: line 2, L=4
  0002.0010  7777777777777700   end-of-file terminator
  ```

  (An earlier revision of this section said "6-bit GOST-packed, 8 chars/word"; the code
  is indeed ГОСТ 10859 but the packing is one char per **byte** — `061 062 060 056 052 040`
  packed six 8-bit bytes per word reproduces `1423106013425040` exactly, and the
  byte-oriented machinery (`FR1x6` char→word division, the per-byte marker mask `МСКМАР`)
  confirms it.)

* **`*` → I / ISO (КОИ-7, «МС Дубна») format** (long path, **~4500 extra instructions** = the
  transcoding pass). The text is re-encoded to a **flat 8-bit KOI-7 byte stream, 6 bytes per
  word, each line `\n`-terminated (`0x0a`)** — no line numbers, no length prefixes. Confirmed
  in zone 1 / zone 3:

  ```
  0001.0000  … 43 54 50 4f 4b 41   KOI-7 "C T P O K A" = СТРОКА
  0001.0003  … 31 83 0a            … ends with 0x0a (newline)
  0001.0011  … ca 0a 0a            line 2 end
  ```

So the У form is the **internal editor image dumped as-is** (compact, numbered, ГОСТ-byte);
the I form is a **portable text serialization** (KOI-7 bytes, newline-delimited). This is the
write-side counterpart of the `РЕД`/`РЕД/*` read-side encoding choice (§8f).

### Zone 0 is protected — the `<ЗОНА>=0` write is a no-op
Both `К 1234 0000` (У) and `К 1234 *0000` (I) **write nothing**: the write control word
collapses to `0040000000000000` (phantom LUN 0) and **no zone changes anywhere** on the
volume (verified by dumping zones 0–13 before/after). Zone 0 is the catalog/archive zone
(§8e), so a raw file write there is refused. Writes succeed only for **zone ≥ 1** — verified:
У→zone 2, I→zone 1, I→zone 3 all wrote correctly, while У→zone 0 and I→zone 0 were no-ops.
(So the intuitive "`К 1234 0000` makes a У file in zone 0" does **not** hold — pick a nonzero
zone.)

New symbols from this trace: `ЧТНД`/`ЗПНД` (`02450`/`02451`, volume read/write Э70 templates),
`КОНФ` (`02453`, У-file end terminator).

## 8h. Encrypted files — the `З` flag and the cipher, traced

Manual §6.2.4: `СФ <ИМЯФ> <КЗОН> [У|I|К] [З]` — the trailing **`З`** makes the file
**encrypted** ("файл будет шифрованным"). Encryption is password‑based and only usable in a
**keyed library**. The full working session (`dispak dimip.b6`, teletype on stdout,
`-t -t` trace on **stderr**):

```
$КТ 1234 0 100        create catalog on vol 1234
ПОЛ А Б               register библ А WITH key Б         (keyed library is required)
ВОЙ А Б               log in — needs the key, else "ЧУЖОЙ КЛЮЧ"
СФ ФШ 10 У З          create encrypted У file ФШ (10 zones); СФ lists it as  "ФШ↑ …"
РЕД ФШ / Б            edit — the "КЛЮЧ" prompt takes the key Б
…text…                (empty line ends input)
К / Б                 write — "КЛЮЧ" again; the FIRST К returns error "КО 003",
К / Б                 the SECOND К succeeds (quirk: it works the second time)
ВЫЙ
```

Observed facts:
- **Flag.** The `З` flag sets bit **`0002` (bit 38)** of the file's 2‑word directory entry —
  mask **`МШИФР` (`D02433` = `0002000000000000`)**. Confirmed by diffing entries:
  `ФШ`(encr)=`4002…` vs a plain file=`4000…`. The `СФ` listing renders an encrypted file with
  a trailing **`↑`** (`ФШ↑`).
- **Access gate.** Every `РЕД`/`К` on the file tests the flag at `02672` (`и МШИФР` →
  `уза` skips when clear) and, if set, emits the **`КЛЮЧ`** prompt (`02507`), reading the key
  via `Э53`. The typed key is packed into **`РКЛЮЧ` (`'1561'`)**. The library key itself is set
  by `ПОЛ <идпол> <ключ>` and demanded again by `ВОЙ`.
- **Storage.** File **content lives on the scratch archive (LUN 40)**, not on vol 1234 — only
  the catalog/directory persists there, so dumping vol 1234 never shows file bytes; content is
  observed via a same‑session read‑back (`РЕД`+key → `Л`).

### The cipher (`ШИФР`, `03121`) — dynamically confirmed
Called on write (and read) of an encrypted file; skips via `по G03133` when `и МШИФР`=0.
It (de)ciphers the `070000` I/O buffer word‑by‑word using the BESM‑6 gather/scatter
instructions (`сбр`/`рзб` = pack/unpack under mask, like PEXT/PDEP):

```
РКЛЮЧ   = packed password                         (e.g. 1037740000000000)
ИНКЛЮЧ  = РКЛЮЧ ⊕ ВСЕЕД = ~key                     (D02370)
М11     = popcount(~key)   (acx)                   (e.g. 046 = 38)
per word W:  W' = сбр(W,~key)  |  (сбр(W,key) << М11)
```

i.e. a **key‑controlled stable bit‑partition of each 48‑bit word**: the bits at key‑`0`
positions are packed into the low `popcount(~key)` bits and the bits at key‑`1` positions into
the high bits — a reversible permutation. Verified live: a plaintext line‑header word
`0047300000000107` → `0100000000216166`. Decryption applies the inverse (scatter, `рзб`,
`G04645`). Wrong key ⇒ the inverse permutation is wrong ⇒ unreadable content, which is the
point of §6.2.7.12 ("если файл шифрован … необходимо установить пароль").

New symbols: `ШИФР` (`03121`), `РКЛЮЧ` (`'1561'` working key), `МШИФР` (`02433` flag mask),
`ИНКЛЮЧ` (`02370` ~key scratch).

## 8i. The МКП macroprocessor (the `<` scenario language), traced

Manual §6.2.7: МКП interprets a file whose lines start with `<` as macro directives
(`<ХХХ[=АRG]...`); all other lines are copied to the temp area. **Working session**
(`dispak -t -t dimip.b6`, stdout=dialogue / stderr=trace):

```
$КТ 1234 0 100 / ПОЛ А Б / ВОЙ А Б     (library, as in §8h)
СФ МК 2 У
РЕД МК
<   проба мкп                          comment («<» + 3 spaces)
<LЕТ=П10=123                           МП10 := "123"
<АDD=П10=5                             МП10 := "128"
<МЕS=ЗНАЧ %П10                         → prints "ЗНАЧ 128"  (%-substitution)
<IGЕ=П10=100                           128 ≥ 100 → true
<МЕS=ДА                                → prints "ДА"
<ЕLS / <МЕS=НЕТ / <ЕND                 "НЕТ" is NOT printed (branch skipped)
<МЕХ                                   exit МКП → ДИМИП '*' prompt
(blank) / К / К                        (first К → «КО 003» quirk; second succeeds)
МК                                     ← invoking the FILE NAME enters the МКП
ВЫЙ
```

Confirmed mechanics (addresses in `dimip.lst` / `dimip.notes`):

- **Entry** (`03224`): a directive that fails the `ТАБДИР` scan is treated as `<ИМЯФ>` —
  file call. Init: `М17:=01415` (МКП context), КОТ:=0, condition scale `'1560':=0`, cell 1
  (`VАР00`) := default directive char `<` + МП char `%`; then catalog search + line loop.
  (`<МК` at the prompt is NOT the call syntax — it errors `ФАЙЛА <МК НЕТ`; bare `МК` is.)
- **Command table `КЛЮКОМ`** (`02173`–`02227`, 29 keys, high 24 bits = 3 GOST chars):
  `SIТ SТ NАМ SUВ INF МUL МЕХ '   ' DIV RЕР АDD LЕТ СLО UNР SWI МЕS WRI GЕТ FIN СОN СНЕ
  FОR ОРЕ RЕА LАВ IGЕ ЕLS IЕQ ЕND`. vs the manual: **no** `UNТ/SIZ/RАN/МСR/МЕN`;
  **undocumented** `СОN`, `СНЕ`, `LАВ` (`LАВ` closes a `RЕР` loop = the manual's `UNТ`).
  Parallel `АДРКОМ` (`02237`–`02273`) holds handler addresses + pre-dispatch flags.
- **Line processing** (`МКПСТР 02537`): non-`<` lines → temp area (`LNTMP`); `<`-lines →
  `СКНКОМ` → `ДСПКОМ` → handler; unknown `<ИМЯМ` (with М12=0) → `МАКВЫЗ 02566` = nested
  macro call. Handlers return via `СЛДСТР 02536` (also the comment handler); end of file /
  `<МЕХ` → `КОНМАК 03673`: decrement macro-call level (byte of cell 1), level 0 → `ГЛЦИКЛ`.
- **Macro variables**: `МПn` = 4 words at cells `4n+1..4n+4` (`VАР00`=1–4, `МП10`=51₈–54₈,
  verified); `АДРМП 04102` resolves n→М4. Text УПП, `0377` terminator. КОТ = byte of
  `VАР00` word 1 (`УСТКОТ G04333`).
- **`%`-substitution** happens while *reading* the line (`G03717`): `%` + octal digit ⇒
  `%ККК` = 3-octal-digit char code (a non-digit there → **`НЕВРН КОНСТ`**, `G02055` — hit
  by typing `%10`); `%` + letter ⇒ МП name, its content is spliced into the line (`%П10`→`128`).
- **Conditionals**: cell `'1560'` is a **shift-register stack of nesting bits** (bit0: 0 =
  execute, 1 = ignore; depth ≤47 = 48-bit word). `IЕQ/IGЕ` push 0; a false condition jumps
  into `КОМЕLS` which **inverts bit0**; `ЕND` pops (shift right). While ignoring, `МКПСТР`
  scans only the last 4 keys (`М13=-3`: `IGЕ ЕЛS IЕQ ЕND`) — everything else is skipped
  (verified: the `<МЕS=НЕТ` between `ЕLS`/`ЕND` never reached `ДСПКОМ`).
- **Channels** (`ОРЕ/RЕА/WRI/FОR/FIN/СЛО`, НК=1..3): per-channel block at `'1557'+20₈·N`
  (`1577/1617/1637`): Э70 descriptor, line counter, file cipher key. Encrypted files are
  de/re-ciphered per zone on channel I/O (`G04552`/`КОМСЛО` use `рзб`/`сбр` with `ИНКЛЮЧ`,
  same permutation cipher as `ШИФР` §8h). КОТ 3 «канал не открыт»; КОТ 4 on wrong mode is
  the `ДСПКОМ` default М16 (see the `СНЕ` subsection below), not a dedicated code.
- **Arithmetic** (`АDD/SUВ/МUL/DIV`, adjacent handlers `03777`–`04003`): integers as decimal
  text, shared tail `G04007/G04011` converts result back to text into the МП.
- **New coverage cases from `dimip.uncov`**:
  `<UNР=П16/П30=.` over `A.B` exercises the alternate-output path (`04454`) where the
  split uses `П16` as the input but writes output starting at `П30`; the input remains
  unchanged (`UNРВ А.В А` in `mkp.out`). A later fixed-name probe confirmed the sequence:
  `<UNР=П60/П70=.` over `A.B.C` leaves `П60=A.B.C` and writes `П70=A`, `П71=B`, `П72=C`,
  with count `П01=3`. `<SWI=П10=89=90` exercises the matching-switch path
  (`04476`, `04477`, `04500`, `04503`, `04504`), executing only the selected next line
  (`SWI1`) before resuming after the skipped alternatives. `<МЕS/Р=PRINTCOV` exercises
  the printer-output path through `Э64 D02376` (`04172`, `04173`, `04174L`).
- **Coverage probes that did not help yet**:
  the documented `LЕТ=П19=П18/2=Б` form works and prints the selected byte as decimal
  (`34` for `ABCDE` byte 2), but it still takes the nonzero-byte path and leaves
  `04150`-`04152` uncovered. `П18/6` and uninitialized `П22/1` read as `255`, not zero.
  `<UNР/Б=П17=.` over `A.B` works (`UNPБ2 А В`) but does not reach the remaining
  `04464` branch; further probes with `A..B` and `.A.` show `/Б` is inert in this binary
  and empty fields are preserved with or without it.
- **`СОN`** (`КОМСОN 04421`) is an undocumented **substring search**:
  `<СОN=VАР=TEXT` searches the text value of `VАР` for literal `TEXT`; on success it writes
  the **1-based** first-match position into `МП01` (`VАР01`), and on failure leaves `МП01`
  as `НЕТ`. It is not a variable-to-variable compare: `<СОN=П10=П10` searches for the
  literal text `П10`. Verified cases: `ABABA/BA -> 2`, `ABABAC/ABAC -> 3` (backtracking),
  `ABABA/Z -> НЕТ`.

New symbols: `КЛЮКОМ` (02173), `СЛДСТР` (02536), `МКПСТР` (02537), `МАКВЫЗ` (02566),
`КОНМАК` (03673), `АДРМП` (04102). All 28 `КОМxxx` handlers annotated in `dimip.notes`.

### `<СНЕ=МП=Т` — the CHECK command decoded (static; error path traced)

`СНЕ`, undocumented in the manual, is a **type/character-class validator**. Its class
table is `CHKTAB` — the upper halves of КОИ7-table rows А–Г (`02135`–`02140`), yet another
dual-use overlay. Each entry packs `[key letter][0o200 − class limit]` into bytes 1–2:

| row | key (byte 1) | byte 2 | limit | class |
|-----|:--:|:--:|:--:|-------|
| `02135` (А) | `В` | `170` | 8 | octal digits 0–7 |
| `02136` (Б) | `I` | `166` | 10 | decimal digits 0–9 |
| `02137` (В) | `R` | `160` | 16 | digits + numeric punctuation `+ − / , . ⏨` (ГОСТ 000–017) — real-number syntax |
| `02140` (Г) | `Р` | `176` | 2 | binary digits 0–1 |

`ДСПКОМ` enters **every** handler with `уиа 4(М16)` (`03754`), and `КОМСНЕ` (`04436`)
uses that as the table length: it scans indexes 3→0 (`слиа -1(М16)`; exhaustion →
`G02055` «НЕВРН КОНСТ»), matching `АРГ2` against the key byte (`сда 64+40; нтж АРГ2`).
Row Д (`02141`) at index +4 is **outside** the array. On a match, `РАБ` = bytes 1–2
(`сда 64+32`), and the loop at `G04443` walks АРГ1's ГОСТ bytes with the
add-and-test-bit-8 trick: `byte + (0o200 − limit)` sets bit 8 (`и D02436`) iff
`byte ≥ limit`; the OR-accumulated result (`сда 64+7` → 0 or 1) goes to **КОТ** via the
`G04334` entry of `УСТКОТ`. So `<СНЕ=Пхх=Т` leaves КОТ = 0 if Пхх consists solely of
characters legal for type `Т`, 1 otherwise — input validation for `<GЕТ`-obtained values,
made one-compare-per-char by ГОСТ's layout (digits `000`–`011`, numeric punctuation
`012`–`017`). The `0o377` terminator can't false-trigger: `0o377 + complement ≥ 0o400`
keeps bit 8 clear for all four entries.

Dynamically confirmed on the error path only: `mkp.txt`'s `<СНЕ=П10=НЕЧТО` prints
«НЕВРН КОНСТ» (a multi-char `АРГ2` can never equal a key byte, so М16 runs out). The
valid-key path is static analysis. Two side notes: byte `170` in row А equals the
cursor-left code by **coincidence** (it is `0o200−8` here); and since `ДСПКОМ` presets
`М16 = 4`, the channel «КОТ 4 wrong mode» is really the *inherited default* М16 — any
handler that error-exits through `УСТКОТ` (`G04333` = `счи М16`) without setting М16
reports 4.

### 8j. Low-core map (cells below the 02000 load address)

All identified low-core cells, with the evidence for each (octal addresses). The `МП00`–`МП03`
names are **documentation-only** (not in `dimip.sym`: naming cells 1–15 would make `findsym`
render every small literal operand — `слиа 1(М5)`, `уиа 4(М16)`, … — as `МПxx+k`):

| Cell(s) | Name | Meaning / evidence |
|---------|------|--------------------|
| `0001`–`0004` | `МП00` | `VАР00`, МКП variable 0: word 1 holds the МКП directive char `<` (byte 1), macro-call level (byte masked by `D02441`, decremented by `КОНМАК`), КОТ (written by `УСТКОТ G04333`), МП char `%` (byte 6). Initialized at МКП entry (`03234`). |
| `0005`– | `МП01` | `VАР01`: `<INF` puts the current time here; `<ОРЕ` (no-channel form) the file start zone; **`ДИРФ` stores the formed task number here** (`зп 5` — cf. §6.2.6, ДИМИП passes data to macros via VАР01). |
| `0011`– | `МП02` | `VАР02`: `<INF` — monitor шифр; `<ОРЕ` — file length. |
| `0015`– | `МП03` | `VАР03`: `<INF` — date (2 words, `0015`/`0016`); `<ОРЕ` — file type. |
| …`0620` | — | МПn = cells `4n+1..4n+4` (verified: МП10 = `0051`–`0054`); 100 vars max. |
| `1322`–`1337` | `АРГСТР` | Copy of the МКП line words `СТРОКА+1..+14` (made at `G02547`); byte-wise argument extraction reads it via base `АРГСТР-1(М16)` (`G04121`). |
| `1347` | `КОМАНД` | packed directive/command token (parser). |
| `1350`–`1352` | `АРГ1`–`АРГ3` | parsed argument tokens; cells up to ~`1406` hold further args/flags (`АРГ3+21` UNР delimiter, `АРГ3+22` МЕХ/МЕS arg, `АРГ3+26` ДИРФ/РЕД format flag, `АРГ3+27/28` LЕТ index args). |
| `1556` | `ОПЗОН` | Э70 descriptor of the *current zone being read* (МКП file / editor); saved+restored by `RЕР`/`LАВ` frames; written + exchanged at `G04642`. |
| `1557` | `ОПКАН` | base of the per-channel blocks: channel N (1–3) block at `ОПКАН+20₈·N` (`1577/1617/1637`): +0 Э70 descriptor, +1 line counter / open flag, +3 file cipher key. N=0 slot = the temp area itself. |
| `1560` | `ШКУСЛ` | МКП condition-nesting scale (shift-register stack; §8i). *Beware:* rendered `ШКУСЛ(М13)` in channel code it is the channel's +1 slot, not the scale. |
| `1561` | `РКЛЮЧ` | working cipher key (§8h). |
| `1562`–`1565` | — | (`РКЛЮЧ+1..+4`) `RЕР` loop frames grow *down* from `1562` in 4-word steps. |
| `1707` | `ПРЕФ` | `$`-prefix flag (`ФЛАГД`); `ПРЕФ-1` caches the МП char `%` during МКП line processing. |
| `1715` | `ОПВЫВ` | Э71 descriptor: terminal line output (`*71 1715` throughout the traces). Head `+0..+2` = the Э71 descriptor words; `+3`/`+4` are repurposed as subtask state (below); the tail `+5..+16` is a block of loosely-related monitor state cells, each named individually below. |
| `1720` | `НКАН` | subtask channel number `<NК>` — `ДИСПАТ` packs `АРГ1`'s value into the top byte (`сбр D02442; сда 64+36`), i.e. the `Э62` channel-argument field; read by every ПЗ op (`Б`/`ЗП`/`ПП`/`ВЫБ`, `ПЗНОВ`/`ПЗСТОП`, `G05127`→`Э50 151`). Was `ОПВЫВ+3`. |
| `1721` | `ТЕКПЗ` | channel of the currently-active (terminal-owning) subtask, `0` = none. `ПЗНОВ` claims it, `ПЗСТОП`/`G03603` release it (`нтж НКАН`), `ДИРЗП` uses it for `Э62 46` terminal handover; `ДИРФ`'s `Ф/*` also writes it. Was `ОПВЫВ+4`. |
| `1722` | `ОПВЫВ5` | (`ОПВЫВ+5`) placeholder — thin evidence: only site is `мод ОПВЫВ5` in `ДИРС` (an index/address operand). Kept named so the tail doesn't re-anchor. |
| `1723` | `ТЕРСОБ` | (`ОПВЫВ+6`) terminal-exchange event bits — `ДЕШСОБ` latches them into the gathered event word (`или ТЕРСОБ` at `03474`; bit r.11 is staged here at `03476` before `ПЗНОВ`). Was `ОПВЫВ+6`. |
| `1724` | `ОПВЫВ7` | (`ОПВЫВ+7`) placeholder — thin evidence: `ОТКНД` scratch around the `Э62 60` (data-set LUN 60) release. |
| `1725` | `ШКПЗ` | (`ОПВЫВ+8`) scale of subtask shifrs/channels — `ПЗНОВ`: `сч ШКПЗ / Э62 61 (запрос шифров ПЗ) / зп ШКПЗ`; `ДИРПП` toggles a channel bit (`нтж ШКПЗ`). Was `ОПВЫВ+8`. |
| `1726` | `ОПВЫВ9` | (`ОПВЫВ+9`) placeholder — thin evidence: sparse ПЗ-context scratch (init-zeroed; `G03610 сч`). |
| `1727` | `ПАДМ` | (`ОПВЫВ+10`) administrator password — loaded from the catalog at init (`2036: сч БУФЕР+3`); `ДИРД` compares `АРГ2` against it (`нтж ПАДМ` at `05727`) and `ПОЛ` uses it for administrator authorization. `G05722` compares `АРГ3` with `ПАДМ`; in the traced `К 1234 *0010 адм` probe the subsequent `АРГ2`-derived descriptor rolls through `Э70 ОПЗОН` until `ОШ.В ИНФ.СЛ.ЭКСТ`. Was `ОПВЫВ+10`. |
| `1730` | `ГОТБУФ` | (`ОПВЫВ+11`) ПЗ output-buffer-ready flags — `сч ГОТБУФ`, r.4 «буфер вывода готов» → `G03530`. Was `ОПВЫВ+11`. |
| `1731` | `ОПВВ12` | (`ОПВЫВ+12`) placeholder — tentative: a field of the `Э50 114` (date + machine-number) result (`и D05756`), feeds `ДАТА` and is OR'd into headers (`G05656/G05715`). Not firmed up (date component vs. machine number). |
| `1732` | `ОПВВ13` | (`ОПВЫВ+13`) placeholder — thin evidence: set once at init to `'F'` (`ENDMRK = 0100`) and apparently never read. |
| `1733` | `ЗАПБУФ` | (`ОПВЫВ+14`) `Э62 41` buffer-read request base word (`катномер:32-25 \| тип/лист \| D02356`); `ДИРБ` bumps the zone number (`слц ОДИН`) until `Э62 41` returns «нет зоны». Was `ОПВЫВ+14`. |
| `1734` | `СЧСТР` | (`ОПВЫВ+15`) output line/string counter — `G04701`: `сч СЧСТР / слц ОДИН / зп СЧСТР` (increment), reset by `ДИРПЕЧ`/catalog ops, feeds number formatting (`G03032`). |
| `1735` | `ТОМКАТ` | (`ОПВЫВ+16`) `Э50 131` catalog-volume attach word (LUN + BCD том) — `ПОДКАТ`: `сч ТОМКАТ / Э50 131`; set by `ДИРКТ` from `<ТОМ>`. |
| `1736` | `ОПФАЙЛ` | Э70 descriptor: library-file zone exchange (`ШИФР` increments the zone in it; `ДИРФ` builds the Э50 7701 control word from it). |
| `1741` | `ОПКАТ` | Э70 descriptor: catalog zone 0 exchange. |
| `1746` | `СТРОКА` | current-line buffer. |
| `1774` | `РАБ` | scratch; also the Э71 *input* descriptor (`*71 1774` in `ЖДИКОМ`). |
| `1411`–`1416` | — | (unnamed) М17-workspace: main loop sets `М17=1411`, МКП sets `М17=1415`; used as operand scratch `(М17)` by the arithmetic/compare handlers. |

## 8k. Subtask (ПЗ) event handling

ДИМИП runs as the **главная задача** (main task); a task formed by the `Ф` directive whose
passport carries a `ГЛА <шифр ДИМИПа>` section becomes ДИМИП's **подчинённая задача (ПЗ)**
(subtask). The OS notifies the main task about its subtasks through the **event scale**
(шкала событий), and ДИМИП handles those events through an event decoder.

**Setup (init, `02017`–`02021`).** Three `Э53` calls arm the mechanism:
`Э53 21` объявить события with `ВСЕЕД` (all bits); `Э53 11` set decoder address `= М15 = 03474`
(`ДЕШСОБ`), whose 0o11-cell save field sits just before it (`пам` at `03462`); `Э53 12` mask
`= D05771 = 0o6615`. The decoder's own gather-mask is `D05767 = 0o6614` (the `Э53`-12 mask minus
bit 1, the alarm — which is serviced by the `Э53 17` wait itself, not gathered).

**Recognized event bits — read out of the code, not the manual.** `D05771 = 0o6615` selects
exactly the event-scale bits **{1, 3, 4, 8, 9, 11, 12}**; `D05767 = 0o6614` is the same set
minus bit 1. To find which handler each bit reaches, follow the two decoder transforms:

- `сбр D05767` (BESM-6 `apx`) compacts the gathered bits toward the senior end, preserving their
  high→low order, so event bits `12,11,9,8,4,3` land in word bits `48,47,46,45,44,43`
  (measured: an event in OS bit 4 yields word bit 44).
- `нед` then returns `М16 = 49 − wordbit` (measured: word bit 44 → `М16` 5, word bit 43 → 6),
  and `пб 03503(М16)` jumps to `03503+М16`.

Composing the two gives the full bit→handler table (all arithmetic code-derived; the
`bit 11 → ПЗНОВ` row is independently confirmed by the manual, where OS event **bit 11 =
"появилась ПЗ"**, §5.3.85/86):

| event bit | `М16` | slot | handler / meaning |
|-----------|-------|------|-------------------|
| **12** | 1 | `03504` | message → print ` БИБЛ:` (`D02333`) via `G02060` |
| **11** | 2 | `03505` | **`ПЗНОВ` — «появилась ПЗ»** (subtask appeared/detached) |
| **9**  | 3 | `03506` | **`ПЗСТОП` — subtask stopped / aborted** |
| **8**  | 4 | `03507` | task end (`Э62 0`) |
| **4**  | 5 | `03510` | output buffer ready → `G03530` |
| **3**  | 6 | `03511` | terminal exchange (`Э71 ОПВЫВ`) |
| **1**  | — | — | будильник (alarm) — masked but not gathered; wakes the `Э53 17` wait |

`ДЕШСОБ` masks `ТЕРСОБ` (`ОПВЫВ+6`, `aox` at `03474`) into the gathered word to inject the terminal-exchange
bits; in the baseline (no-subtask) sessions only bits 3 and 4 fire (`М16` = 6, 5), trace-verified.

**Path to `03536` / how `АРГ3+26` (`01404`) enables it.** Word `03536` is not reached by the
directive dispatcher directly; it is on the output-buffer-ready event path:

```
ЖДИКОМ 03331/03332  Э71, then Э53 17 wait
  -> ДЕШСОБ 03474   gather events into D02327
  -> 03477..03503   pick event bit 4 => М16=5
  -> slot 03510     сч ГОТБУФ (ОПВЫВ+11); пб G03530
  -> G03530         service output-buffer counter / Э71 output
  -> 03535..03536   if G03323 returns zero, clear СТРОКА+10.. via loop at 03536
```

The precondition for this path is set earlier by `ДИРФ`. After successful `Э50 7701`,
`ДИРФ` stores the formed task number in `VАР01` (`03434: зп 5`) and tests
`АРГ3+26`:

```
03434r  сч АРГ3+26
03435   по ГЛЦИКЛ        ; zero: plain Ф, no extra setup
03435r  сч D02342
03436   Э50 7710         ; nonzero: take the output-buffer setup path
...
03442   зп ТЕКПЗ
        пб ГЛЦИКЛ
```

`01404` (`АРГ3+26`) becomes nonzero in the shared lexer, not in `ДИРФ` itself. Parser setup
clears the argument scratch area at `03165`–`03166`, including `АРГ3+26`; slash-style trailing
modifiers are then stored indirectly by `03203: зпм 24(М11)` (`/` separates the modifier, which is
packed and left in `АРГ3+26`). **Confirmed by trace** (`dispak -t -t`, WORK volume): `ф тест`
loads `АРГ3+26 = 0` and fires only `03431: *50 7701`; **`ф/пз тест` (`АРГ3+26 = 027447`) and
`ф/* тест` (`АРГ3+26 = 031`) each fire `7701` then `03436: *50 7710`**. So any `Ф/<mod>` form is
plain `Ф` plus a follow-up `Э50 7710`, gated by `АРГ3+26 ≠ 0`.

The designed modifier is **`ПЗ`**, not `*`. After the `7710`, `03440–03441` load the named
constant `ТПЗ` (`D02125`, GOST `ПЗ00≠0`), shift it right 32 to isolate the two chars `ПЗ`
(= `027447`), and XOR it with `АРГ3+26`:

```
03440  сч ТПЗ / сда 64+32   ; acc = 'ПЗ' = 027447   (D02125 >> 32)
03441  нтж АРГ3+26          ; ω = 0  iff modifier == 'ПЗ'
       по ГЛЦИКЛ            ; Ф/ПЗ  → ω=0 → return (no ТЕКПЗ)
03442  зп ТЕКПЗ           ; Ф/* (or any non-ПЗ) → arm the output-buffer-ready event
       пб ГЛЦИКЛ
```

So `Ф/ПЗ` is the intended special case (there is a dedicated `ТПЗ` constant to recognise it):
form + `7710`, then a clean return. `Ф/*` — or any other `/mod` — is the *"not ПЗ"* fall-through:
form + `7710`, then `зп ТЕКПЗ`, which is what arms event bit 4 (`→ 03536`) on the
output-buffer-ready path above. (`АРГ3+26 = 027447` is exactly `ТПЗ >> 32`, so the match is exact.)

### `Э50 7710` — undocumented formation-family follow-up
The МОНИТОР extracode manual documents only `AИСП = 7701` for the formation family (§5.3.67);
the nearest queries are `215` (input-stream info, §5.3.62) and `7702` (where-am-I). **`7710` is
not in the manual**, and **dispak does not implement it** — `extra.c` handles `07701`
(`exform()`) and `07702` and drops everything else into the `E50 %04o` stub (`E_UNIMP`). The
`E_UNIMP` is caught by DIMIP's abort handler and control returns to `ГЛЦИКЛ`, so `03437–03442`
never run live: under dispak both `Ф/ПЗ` and `Ф/*` are indistinguishable from `Ф` (same `ТКН0…`
passport; `7710` just prints `E50 7710`). The `ПЗ`/`*` branch above is visible only statically.

What DIMIP intends by `7710`, read off the usage: it is issued **only after a successful `7701`**,
with `сумматор = D02342 = 7777777700001342` (bits 48–25 all-ones, bits 24–1 = `01342`) — a
query/status-shaped word, not the start/end task-text descriptor `7701` uses (`D02401`,
bits 48–40 = `772` = "form from disk"). Its return is only *inspected and reported*
(`03437 нтж ВСЕЕД / пе G02067` takes an all-ones return to a message template `ЗАГБУФ`), never fed
back into the task text. This reads as a **status/confirmation query about the just-formed task**
(the mirror of the perforation `form ↔ разгрузка` pair) — most pointedly a subordinate-task (`ПЗ`)
receipt, given the `Ф/ПЗ` modifier that requests it; the exact return format is undocumented.

**Bit 11 confirmed on a live subtask.** `dimsession.txt` (`кт work` / `вой а` / **`ф тест`**) run
under `dispak --subtasks` forms subtask `#041` and runs it (~10 000 instructions at PC `012xxx`,
normal completion, no abort). The raw `Э53 17` scale carries the ПЗ event in **low bit 11**
(`0o2010` = bits 11 + 4) at **both** the subtask's appearance and its detach — exactly `bit 11 =
"появилась ПЗ"` (§5.3.85/86), and `сбр`+`нед` route it to `М16` = 2 → slot `03505` as derived.
The slot's `пио G03552(М15)` reaches `ПЗНОВ` when `М15 = 0`: the decoder first latches bit 11 into
`ТЕРСОБ` (`ОПВЫВ+6`, `03476`), then `ПЗНОВ` runs on the next pass. `ПЗНОВ` fired twice — once per transition.

**dispak bug — wrong event bit on subtask termination.** `dispak --subtasks` raises bit 11
(`EVENT_PZ_APPEARED`) at *both* the subtask's appearance **and** its termination (`tasks.c`:191 on
exit, :395 on stop — the only subtask→master signal it emits). Appearance on bit 11 is right, but
**termination is wrong**: DIMIP's decoder routes bit 11 → `ПЗНОВ` (03552), which *starts* the
subtask (`Э62 61/63/64` + `Э53 31 пуск`). The handler that reads a **stopped/finished** subtask is
`ПЗСТОП` (03571) — it issues `Э62 101` (*запрос **остановленных** ПЗ*) and `Э62 54` (stop reason) —
and the decoder reaches it only from **event bit 9** (bit 9 → word 46 → `М16`=3 → slot 03506).
So the **expected event bit for subtask termination is bit 9**, not bit 11. Because dispak sends
bit 11, DIMIP re-runs `ПЗНОВ` (start) on a subtask that has already ended instead of running
`ПЗСТОП`/`КЗПЗ`, and the subsequent `Б`/`Л` directives report `НЕТ П` (no stopped subtask —
`Э62 101` finds none). bit 9 is not named in the extracode manual (which documents 1, 5, 11, 12,
17, 19); it is established from DIMIP's own decoder + the `ПЗСТОП` handler semantics.

**dispak bug — `Э50 151` is a stub, so `Б` sends `Э62 41` a zero queue number.** The `Б`
directive (`ДИРБ` 05051) builds the `Э62 41` argument (fetch a subtask's print stream, 05066)
from `ЗАПБУФ` (`ОПВЫВ+14`), whose high half must carry the subtask's **input-catalog (queue) number**.
Data path: `Ф`→`Э50 7701` returns the queue number in `reg[016]`; to read the buffer, `ДИРБ`
calls `G05127` (05127) = `сч НКАН` (channel) → **`Э50 151`** (§5.3.40, channel→queue number)
→ `и D02362` (`м40в'377'`, top byte 48–41) → `сда 64+16` (right-shift 16, lands in `acc.l`).
dispak's `Э50 151` (`extra.c`:1805) is unimplemented: it returns `E_UNIMP` for any nonzero
channel and a hardcoded `acc.r = 0123` (`/* arbitrary */`) for channel 0 — placed in the **low**
half, which DIMIP's top-byte mask discards → `acc.l = 0`. Trace: `05066: *62 41 acc=…01030000`
(`acc.l = 0`). Two things to fix in dispak: (1) look up the real `t->catno` for the requested
channel (`task_by_catno`/the slot table already hold it) instead of `0123`; (2) return it in the
**top byte (48–41)** where DIMIP reads it — note this differs from the manual's stated `8-1 PP`,
but DIMIP's `и м40в'377'` + right-shift is authoritative.

**Both bugs fixed in dispak and verified** (re-run of `dimsession.txt`, 2026-07). (1) `Э50 151`
now returns `task_self()->catno` / `slot[chan-1].catno` in bits 48–41, so `05066: *62 41` gets
`acc.l = 0o13` (nonzero) and the `Б` directive succeeds. (2) `dispak --subtasks` now raises
**bit 9** on subtask stop: the decoder dispatches `М16 = 3 → 03506 → ПЗСТОП`, which runs `Э62 101`
(finds the stopped subtask, `НКАН = 0o41`) and `Э62 54`, reporting **`КЗ 041 КОНЕЦ ЗАДАЧИ`**.
The full subtask lifecycle now works: appear → bit 11 → `ПЗНОВ` (start); finish → bit 9 →
`ПЗСТОП` (`КЗПЗ`, read buffer/reason). The old `НЕТ П` failure is gone.

**`Б` reading a subtask's output buffer — verified end-to-end.** A batch session issues `б`
before the forked subtask has finished writing `pzNNN.raw`, so `Э62 41` returns `0` ("no zone")
and prints `НЕТ` — a *timing race*, not a bug (the manual: the buffer is readable only "после
остановки этой задачи"). Driving DIMIP through a pty (`expect`, Enter every second until
`КЗ 041 КОНЕЦ ЗАДАЧИ` appears, **then** `б 41`) closes the race: `Э62 41` returns `77777B` and
`л` lists the copied stream (the subtask's `МОНИТОР-80` banner + passport, 4 lines). Two things
the successful run needs, both of which the trace confirms: the **channel** must be given
(`б 41`, not bare `б`) so `НКАН = 41` → `Э50 151(41)` → subtask catno `0o14` → `Э62 41(0o14)`;
and the subtask must have **stopped** so its `pz014.raw` is flushed. The ДИРБ copy path is
annotated in `dimip.notes` (05051–05126): `Э62 41` reads the print zone (type 1) into `БУФЕР`
(page 3 = 06000); `G04636` pulls buffer words, `G03735` packs bytes into `СТРОКА`, and
`LNFIN`→`LNINS` inserts each finished line into the temporary area.

**The decoder `ДЕШСОБ` (`03474`).** ДИМИП does **not** enable async transitions in the monitor
loop; instead `ЖДИКОМ` blocks on `Э53 17` ("закрыть задачу до наступления события", §5.3.79) at
`03332`, and on wake the OS enters the decoder — **trace-confirmed: `03332` → `03474`**, not the
fall-through. It gathers the pending masked events into `D02327` (`сбр` + `ТЕРСОБ`, `ОПВЫВ+6`), then loops
`03477`–`03503`: if `D02327 == 0` it goes back to `Э53 17`; otherwise it pops the senior event
bit (`нед` → `М16`), clears it, and dispatches per the table above.

**`ПЗНОВ` (`03552`)** — react to "появилась ПЗ" by attaching and starting it:
`Э62 61` (query the subtasks' ciphers/channels) → `Э62 63` (set the ПЗ save field, §5.3.128) →
`Э62 64` (set the ПЗ event mask, §5.3.129) → `Э53 31` (start the subtask, §5.3.89). This matches
the manual (§6.2.6): a formed ПЗ "реально начнёт считаться" only after it is started.

**`ПЗСТОП` (`03571`)** — react to a stopped/finished subtask:
`Э62 101` (query stopped ПЗ, §5.3.141) → `Э62 54` (query the abort reason in the ПЗ, §5.3.123) →
`Э50 202` (format the reason text) → `Э62 77` (raise abort, §5.3.140) → `Э62 46` (hand over the
terminal, §5.3.117).

**Manual controls.** The three subtask directives drive the same extracodes explicitly:
`Б` (`ДИРБ` `05051`) copies a subtask's output buffer into the temp area; `ЗП` (`ДИРЗП` `05142`)
finishes/frees a subtask (`Э62 44` → `Э53 30` stop §5.3.88 → `Э53 33` finish §5.3.91);
`ПП` (`ДИРПП` `05157`) starts/stops a subtask and hands it the terminal (`Э53 30/31`, `Э62 72`
§5.3.135). The full `Э53` subtask family (24–34: query/set ПЗ event mask, declare/detach main,
stop/start/finish) is documented in extracodes §5.3.84–5.3.92.

**МКП async layer (not the monitor path).** During `<GET` terminal input, byte 5 of `VАР00`
enables four event→macro reactions (§6.2.7.24): bit 8 `САКП`, bit 6 `ФЗПЗ` (subtask entered
solution), bit 5 `КЗПЗ` (subtask ended), bit 1 `БУДИ` (alarm). The macro bodies are **files in
the filesystem**, not code in the image — a grep of `dimip.bin` for those names finds nothing,
consistent with the manual. Default enabled masks: `САКП`, `ФЗПЗ`, `КЗПЗ`.

New symbols: `ДЕШСОБ` (`03474`), `ПЗНОВ` (`03552`), `ПЗСТОП` (`03571`).

## 8l. МКП file channels — `<ОРЕ` / `<RЕА` / `<WRI` / `<СLО` and the record format, traced

Verified by re-running the `mkp.txt` session (`dispak -p dimip.b6 < mkp.txt`), which
round-trips a file through the channel API — `<ОРЕ=звых=2=W`, two `<WRI`, `<СLО=2`, then
`<ОРЕ=звых=1` and three `<RЕА` — and by dumping what it wrote (ЗВЫХ = volume 1234 zone 4).

### Channel state — 16 words per channel (`М13 = 16·к`)

| cell | role |
|------|------|
| `ОПКАН`+16к (`'1557'`) | Э70 control word: buffer page in the left half, LUN+zone in the right; **CW bit 40 (`Э70` read bit) doubles as the channel direction flag** |
| `ШКУСЛ`+16к (`'1560'`) | current record pointer (absolute address inside the buffer page); 0 = channel closed |
| `РКЛЮЧ`+16к (`'1561'`) | open counter/limit (decremented by `СLО`) |
| `РКЛЮЧ+1`+16к | cipher key from the `/КЛЮЧ` suffix (`АРГ3+28`); nonzero → each zone is decrypted on read (`G04552`) / encrypted on flush (`G04511`), the §8h cipher |
| `РКЛЮЧ+2`+16к … | up to 13 field names set by `<NАМ=к=имя1=…` (`КОМNАМ` 04327) |

### `<ОРЕ` (`КОМОРЕ` 04025) — three forms

- **`<ОРЕ=файл`** (no channel): info only — zone → П01, length → П02, type string
  (`D02143+2`, §8c) → П03 (cells 5/9/13). Live: `БЕЗКАН З=7 Д=3 Т=У`.
- **`<ОРЕ=файл=к`** (no mode letter): **read**. Builds `ОПКАН` = `к<<30 | file base CW`,
  stores the key, toggles the catalog dot bit (§8c), then `G04552` (04552) pages the first
  zone into the buffer (`слц ОДИН` on the zone field + `Э70`, then the key decrypt) and sets
  `ШКУСЛ` to the buffer base. `<ОРЕ==к` (no filename) opens the **temp area** itself
  (`ОПВЫВ7` base) as the channel.
- **`<ОРЕ=файл=к=X`** (any mode letter, e.g. `W`): **write** — `G04076` flips CW bit 40
  read→write. The specific letter **`С`** (matched against the low byte of word `02255` =
  `061` — another low-byte overlay on the МКП dispatch table) first walks headers to the
  end-of-file marker: **append**. Both fall through to the same write setup.

### The record format (= the У native format, §8b/§8g)

What the session wrote into zone 4, read back as `ЧИТ1 89` / `ЧИТ2 1`:

Relevant `mkp.txt` fragment:

```
<ОРЕ=звых=2=W
<NАМ=2=ПОЛЕ=ВТОР
<LET=П10=12345=67890
<LET=П11=100=фывапр
<WRI=П10=2
<WRI=П11=2
<СLО=2
<ОРЕ=звых=1
<NАМ=1=ф1=ф2=ф3=ф4=ф5=ф6
<RЕА=П15=1
<МЕS=ЧИТ1 %П15
<RЕА=П15=1
<МЕS=ЧИТ2 %П15
<RЕА=П15=1
<МЕS=ЧИТ3 %П15
```

```
0004.0000  0000000000000002    header: L=2 words incl. header, record# 0
0004.0001  010 011 377 0 0 0   body: "89" + 0o377 end-of-text, zero-padded
0004.0002  0000000000000002    header: L=2
0004.0003  001 377 002 002 016 003   П11's storage word copied verbatim
0004.0004  7777777700000000    EOF marker written by СLО (= EOFCH<<24)
```

- **Header**: low 6 bits (`МСК6` — encoded as `п'D'`!) = record length **including the
  header**; bits 7–24 (`RECNO`) = record number (`<WRI` writes 0; an extra numeric
  argument, cell `АРГ3+27`, is ORed in `<<6` → numbered records); bits 25–30 = field count
  (consumed only by the symbolic `<RЕА` path, `G04264`; 0 → error 6).
- **Field directory**: for a fielded БД record, the first `field_count` bytes of the body
  are a directory. Directory byte `i` stores **one less than the absolute byte index** of
  field `i`'s first text byte, counted from the start of the record header. `G04264`
  finds the field name, checks `(header >> 24) & 077`, sets up `М16=6`, then falls into
  `G04273`; `G04273` increments `М5` before byte fetch, so a directory byte `007` points
  at byte index `010`. Thus a two-field body can start
  `[007,014,"LEFT=RIGHT",0377...]`, where field 1 starts at byte 010 and field 2 at
  byte 015. `<WRI>` writes an already-formed body verbatim; a macro can form fielded
  records by splitting text (for example with `<UNР>`), computing/prepending directory
  bytes, and then passing that body to `<WRI>`.
- **Body**: ГОСТ 10859 text, one char per 8-bit byte, 6 chars/word, terminated by a
  `0o377` byte. Both
  `КОМWRI`'s and `КОМRЕА`'s copy loops delimit the last word with **`МСКМАР`** (`02445` =
  the high bit of each of the six bytes — only `0o377` has it in normal text), and the
  general byte-fetcher `G04116` (04116) flags `byte == 255` (`слиа -255`) as end-of-text.
  The sequential `<RЕА=П15=1` path copies the full record body until this terminator and
  then advances by the header length.
- **Field separator**: the symbolic-field path uses **GOST code `025`**, i.e. `=`.
  After `<RЕА=VАР=НК=ПОЛЕ` finds the field index (`G04264`), `G04273`/`G04116` fetches
  successive bytes. `G04116` leaves `М11 = byte - 0377`; the copy loop then executes
  `слиа '352'(М11)`, yielding `byte - 025`. Nonzero bytes go through `G04167`; byte
  `025` falls through to `G04262`, writes `МСК8` (`0377`) as the output terminator, and
  stops the field. Thus `WRI` writes text containing `=`, and named `RЕА` treats that
  `=` as the field separator.
- **End of file**: any word with **L = 0 but nonzero content** — `СLО` writes
  `7777777700000000` (three `377` bytes = `EOFCH<<24`), the editor's `К` writes `КОНФ`
  `7777777777777700`; both satisfy the same test (`и МСК6` = 0, word ≠ 0 → `G03527`).
  An **all-zero word** means "zone exhausted": `G04552` pages in the file's next zone and
  the scan continues. Records do not span zones.

**Dynamic BD proof (`bd.setup` + `bd.txt`).** The coverage test creates a real catalog
entry `ФД`, then overwrites its first data zone with three hand-formed fielded records:

```
0001.0000  0000000200000704    count=2, rec#=7, L=4
0001.0001  0160610411240062    directory 007,014 then "LEFT"
0001.0002  0524350220226462    "=" then "RIGHT"
0001.0003  7777777777777777    terminator padding
0001.0004  0000000200001004    count=2, rec#=8, L=4
...
0001.0010  0000000200001104    count=2, rec#=9, L=4
...
0001.0014  7777777700000000    EOF
```

The macro test:

```
<ОРЕ=фд=1
<NАМ=1=F1=F2
<RЕА=П20=1=F1
<RЕА=П21=1=F2
<FОR=1=1
<RЕА=П22=1=F1
<RЕА=П25=1=F2
<FIN=1=TARGET=F2
...
<FIN=1=MIST=F1
```

prints:

```
F1А LЕFТ
F2А RIGНТ
F1В МISS
F2В ТАRGЕТ
FIN2 7/МISS=ТАRGЕТ
FIN3 7/МISТ=RIGНТ
```

This confirms that named `<RЕА` uses the directory to read one field without advancing the
record pointer; `<FОR>` is needed to move to the next record before another named read.
`<FIN>` scans later records by `G04412/G04304` and leaves the channel positioned at the
matched record. The subsequent sequential `<RЕА>` copies the whole matched body, including
the directory bytes; bytes `007,014` render as `7/`.

### `<RЕА` (`КОМRЕА` 04244) — three addressing modes

- **Sequential** (`<RЕА=П=к`): copy the record at `ШКУСЛ` — body words after the header
  into the П variable (или into `СТРОКА+1`, and thence to `МКПСТР` as a scenario line, if
  no variable is given — static reading, not exercised), stopping at the `МСКМАР` word —
  then advance one record (`G04304`). Landing on the EOF word zeroes `ШКУСЛ` (channel
  closed) and takes the `G03527` EOF reaction: the session's third read left П15 stale
  (`ЧИТ3 1`) because `G04567` then returns error 3.
- **By record number** (numeric 3rd arg, `RNREA` 04347): find the zone via the per-zone
  first-record index at `'620'/'621'` (built when temp-area zones are flushed, `ZNFLU`;
  the seek re-points the channel with `ОПВЫВ7`-based zones, so this mode is for the
  **temp-area channel**), `Э70` it in if needed, then walk headers by L (`RNSCN`) to an
  exact match on the record-number field.
- **By field name** (symbolic 3rd arg — digits distinguished from letters by the
  `слц МСКЖ; и МСКМАР` parallel-byte trick): look the name up among the `<NАМ` names,
  then use the header's field count and body directory bytes to set the starting byte
  offset. `G04273` fetches bytes from that offset and `КОМRЕА` copies until GOST `025`
  (`=`). This path does not advance the record pointer; it is an in-place field read.

An extra argument in `АРГ3+27` makes `<RЕА` also store the current record's **number**
(converted to text, `0o377`-terminated) into that variable.

### `<WRI` (`КОМWRI` 04532) and `<СLО` (`КОМСLО` 04505)

`WRI`: copy the variable's storage words verbatim until the `МСКМАР` word, then store the
header **at the record start = length by subtraction** (`вчоб ШКУСЛ(М13)`); page-boundary
overflow flushes the zone (`G04511` 04511: encrypt if keyed + `Э70` write) and retries.
`СLО`: requires a write-mode channel (the `G04567` guard inverted), stores the EOF word
`EOFCH<<24` at the current position, flushes the final zone, decrements `РКЛЮЧ`, zeroes
`ШКУСЛ`.

### Guards, errors, and type handling

`G04567` (04567) resolves `к` → `М13/М12` and returns `CW & Е40`: `КОМRЕА` errors if the
read bit is **clear** (opened with a mode letter), `КОМWRI`/`КОМСLО` if it is **set**.
Channel errors do **not** abort the macro: `G04333` (04333) records the code in a VАР00
field (cell 1) and continues — that is why `<ОРЕ=нетфайл=3` is followed by `ПОСЛЕ-ОШ` in
the live output. Identified codes: 3 = channel not open, 6 = record has no fields;
"4 = wrong direction" is really the default `М16 = 4` preset by `ДСПКОМ` for every
handler (§8i, `СНЕ` subsection) surfacing through the error exit.

`КОМОРЕ` does not check the catalog type
nibble (§8c), and `КОМRЕА` unconditionally parses header words. So a channel can only
meaningfully read **У-format** files (or the temp area); an `I` file (flat KOI-7 bytes +
`0x0a`, §8g) would have its first word misread as a header. The `Т=` info form is the only
type-aware piece of `<ОРЕ`.

## 9. Open questions / next-pass targets

1. **МКП dispatcher and command table (§8a, §8i).** Remaining: the rest of the `АДРКОМ`
   per-entry flag bits; the low 24-bit table embedded in the `КЛЮКОМ` words; the valid-key
   path of `СНЕ`; dynamic verification of `LАВ`/`RЕР` loops, `SIТ`, and channel append mode
   `С`.
2. **Archive/catalog format (§8c, §8e).** Catalog creation, file-entry types, the basic
   bitmap/signature fields, and the named-area `КЛЮЧАР`/`Э63` path are traced. Remaining:
   the rest of catalog control words 0–5, exact tract↔bit mapping, and the full идпол
   record layout including passwords and directory pointers.
3. **Low-core and scratch variables (§8j).** Remaining unnamed or thinly identified:
   М17-workspace `1411`–`1416`, `АРГ3+21..+28`, `ПРЕФ+к`, and the `SIТ` situation table near
   `'1662'`.
4. **Editor/temp-area internals (§8b, §8l).** Remaining: the line-header auxiliary bits
   beyond length/record-number/field-count, the still-uncovered field-count print path
   `05623`–`05627`, and the temp-area zone/list paging performed by `РЕД`.
5. **Subtask event layer (§8k).** Remaining: exercise `ПЗСТОП` (bit 9) via `ПП`/`ЗП` while
   the subtask is still channel-associated, and observe `ФЗПЗ`/`КЗПЗ` macro invocation
   during `<GET`.
6. **Source reconstruction.** Continue replacing anonymous labels/data names in
   `re-dimip.be`, assemble with `asm.pl`, and compare against `dimip.bin`.
