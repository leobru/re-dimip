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
| 02011–02016 | Build flag/mask words (`'1731'`, `'1732'`…) from constants `D02164/D02346/D02347/D02350/D02437`. |
| 02017 | `Э53 21` — **declare/clear events** (init the event scale). |
| 02020 | `Э53 11` — set **event-decoder (дешифратор) address**. |
| 02021 | `Э53 12` — set **event-scale mask** (`D05771`). |
| 02022–02024 | Loop: copy 19-word working table into low core (`'1764'`…). |
| 02025 | `Э50 100` — request **job cipher (шифр)**. |
| 02026 | `Э71 D02504` — first **terminal I/O**; `нед D05742` status check. |
| 02030 | `пв G05216` — call setup subroutine. |
| 02032–02035 | `Э70` disk exchanges (read monitor zones); `пв G03335`. |
| 02040 | `Э67 D02400` — install **debug/abort handler**; info word `D02400 = A(ГЛЦИКЛ)` → after any abort, resume the main loop. |
| 02041–02046 | Final table setup; calls `G02070`, `G03402`, `G02064`. |

In short, init = **fault/abort handling** (Э50 102/103, Э63 3, Э67) + **system info**
(Э50 100/114) + **asynchronous event mechanism** (Э53 21/11/12) + **load monitor zones**
(Э70) + **open terminal** (Э71), then fall through into the monitor proper.

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

## 8. Directive dispatch & data structures (static, manual-guided)

Not exercised by the trace; identified statically and to be confirmed later:

- **Directive dispatcher — decoded** (see §8a below).
- **Archive / catalog** — per the manual, DIMIP keeps its archive in disk zones with a
  catalog (идпол/пароль/file map) in the first zone, accessed via `Э70`. Whether the
  OS-level **`Э63`/`КЛЮЧАР`** area/budget access-control calls (extracodes.txt §5.3.156+)
  are used for this, or only DIMIP's own format, is **open** — the `КЛЮЧАР` constant is
  present but the trace shows only `Э63 3`.
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
 header word:  bits 48..25  auxiliary/flag field (low bits gate special handling in G05621)
               bits 24..7   line NUMBER (18 bits)
               bits  6..1   LENGTH L = total words in the line, incl. header
 + (L-1) words of packed text (KOI-7 for a file opened with `РЕД … *…`)
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
            bits 46-45  type:  0 = У (ГОСТ text) · 1 = К (binary) · 2 = I (ISO text)
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

### The У vs I fork (gated by the `*` type flag)
`ПОДКАТ` (`03665`–`03671`) tests the `*` type flag — parsed into the **ПРЕФ area, cell
`'1711'` (ПРЕФ+2)**, exactly the trailing-modifier mechanism of §8f — and forks:

* **No `*` → У / ГОСТ native format** (short path, ~300 instrs). The temp area is written
  **verbatim in DIMIP's native line format**: each line = one header word (line number in
  bits 24-7, length `L` in the low 6 bits) followed by `L-1` words of **6-bit GOST-packed
  text (8 chars/word)**; the file ends with the terminator `7777777777777700` (`D02453`).
  Confirmed by writing to zone 2 (`besmtool dump 1234 --start=2 --length=1`):

  ```
  0002.0000  0047300000000104   header: line 1, L=4  (=1 header + 3 text words)
  0002.0001  1423106013425040   GOST "СТРОКА ПЕРВАЯ" …
  0002.0004  0047300000000204   header: line 2, L=4
  0002.0010  7777777777777700   end-of-file terminator
  ```

* **`*` → I / ISO (КОИ-7, «МС Дубна») format** (long path, **~4500 extra instructions** = the
  transcoding pass). The text is re-encoded to a **flat 8-bit KOI-7 byte stream, 6 bytes per
  word, each line `\n`-terminated (`0x0a`)** — no line numbers, no length prefixes. Confirmed
  in zone 1 / zone 3:

  ```
  0001.0000  … 43 54 50 4f 4b 41   KOI-7 "C T P O K A" = СТРОКА
  0001.0003  … 31 83 0a            … ends with 0x0a (newline)
  0001.0011  … ca 0a 0a            line 2 end
  ```

So the У form is the **internal editor image dumped as-is** (compact, numbered, GOST-6);
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

## 9. Open questions / next-pass targets

1. **Dispatcher decoded (§8a).** Remaining: trace each individual directive handler; fully
   decode the per-entry **flag bits**; identify the adjacent table at `02256`–`02273` (same
   layout but its low-15 fields are not code addresses) and the keyword block at
   `02176`–`02226`.
2. **Archive (§8c, §8e):** catalog *creation* now traced (`$КТ`/`ПОЛ` build zone 0 in `06000`
   and write it via `ЗАПКАТ`; volume attached with `Э50 131`). Confirmed fields: `<ДАРХ>` at
   word `0002`, free-tract **bitmap** at `0005`–`0006`, `*ДИМИП` signature + идпол name at
   `0035`/`0036`. Remaining: the rest of the catalog **control words** (0–5), the exact
   **bitmap** encoding (tract↔bit), the full **идпол record** layout (passwords `<КЛЮЧ>`/`<ПАДМ>`,
   directory pointers — exercise `ПОЛ <ИДПОЛ> <КЛЮЧ> <ПАДМ>` with full params), and whether the
   OS `КЛЮЧАР`/`Э63` access control is used at all.
3. **Name the low-core working variables** (`'1346'`, `'1350'`, `'1715'`, `'1774'`, …) once
   their meaning is established.
4. **Verify the text encoding** of the keyword table (`02176`–`02226`) and re-decode.
5. **Editor internals (§8b):** meaning of the line-header **auxiliary field** (bits 25–48);
   the exact character packing per encoding (KOI-7 / GOST / ТЕКСТ); and the
   временная-область **zone↔лист paging** that `РЕД` performs (the `Э70` window management).
6. Eventually: hand-edit `dimip.lst` into a `dimip.be` source and round-trip it through
   `asm.pl` + `verify.pl` (re-dispak workflow) to a byte-exact rebuild.
