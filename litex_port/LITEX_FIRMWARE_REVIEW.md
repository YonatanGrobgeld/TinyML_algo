# LiteX Firmware Integration Review — TinyML_algo

**Target:** Nexys4DDR + VexRiscv (RV32IM), bare-metal.  
**Scope:** Verify algorithm code in `litex_port/` and document expectations for LiteX SoC/firmware glue (build, UART, startup) that lives outside this repo.

---

## 1) Checklist (PASS / FAIL / N/A)

| # | Item | Status | Reference / Notes |
|---|------|--------|-------------------|
| **1. LiteX SoC target & build** | | | |
| 1.1 | Locate LiteX SoC target script (e.g. nexys4ddr.py) | **N/A** | Not in this repo. SoC build is on the “friend’s” side (e.g. `litex-boards/litex_boards/targets/nexys4ddr.py` or custom). |
| 1.2 | Identify CPU variant, sys clk, memory map, peripherals | **N/A** | Same; would come from that target and `generated/` output. |
| **2. Firmware build system** | | | |
| 2.1 | Locate firmware Makefile / linker script / startup (crt0) | **N/A** | No Makefile, no `linker.ld`, no `crt0` in this repo. Only `pulp-transformer/Test/Helpers/Makefile` (unrelated). Firmware build is external. |
| 2.2 | No glibc/newlib syscalls unless provided | **PASS** | `litex_port/*.c` use only `stdint.h` and local headers; no `printf`, `malloc`, `fopen`, `time`, `errno`. See Section 2 evidence. |
| 2.3 | No printf/malloc/free/fopen/time/errno in firmware | **PASS** | Grep: only comment in `main.c` line 3 (“no malloc, no printf”). No usage in code. |
| 2.4 | Only safe headers; no string.h or local implementation | **PASS** | Includes: `stdint.h` only (+ local `tinyformer.h`, `demo_*.h`, `trained_weights.h`). No `string.h`; no `memcpy`/`memset` in `litex_port/`. |
| **3. UART integration** | | | |
| 3.1 | Uses LiteX generated CSR (csr.h / generated/) | **FAIL** | Not in repo. `main.c` and `demo_main.c` implement UART as **stubs** (no `csr.h`, no MMIO). See `main.c:14–18`, `demo_main.c:17–21`. |
| 3.2 | uart_write_char uses LiteX UART TX + TX-ready correctly | **N/A** | Stub only; real implementation must be added using LiteX CSR API (see Section 5). |
| 3.3 | Interrupt/event usage correct if used | **N/A** | No interrupts in repo; polling is the standard LiteX bare-metal pattern. |
| **4. Compilation & linker** | | | |
| 4.1 | Flags: -ffreestanding, -nostdlib, -march=rv32im, -mabi=ilp32 | **N/A** | No build system in repo. Friend’s firmware build must use these (or equivalent) for bare-metal. |
| 4.2 | Linker script places .text/.rodata/.data/.bss correctly | **N/A** | No linker script in repo. Must match SoC memory (BRAM or DDR per LiteX config). |
| 4.3 | Startup sets SP, zeros .bss, copies .data | **N/A** | No crt0/startup in repo. LiteX firmware typically provides this. |
| **5. TinyFormer integration** | | | |
| 5.1 | All litex_port/*.c compiled into firmware | **N/A** | Repo only provides sources; build is external. List: `tinyformer.c`, `main.c` or `demo_main.c`, `trained_weights.c`, `demo_samples.c`, `demo_classifier.c`. |
| 5.2 | USE_TRAINED_WEIGHTS=1 passed for demo | **N/A** | Build system must define this when building the UCI HAR demo. |
| 5.3 | No missing symbols; no host-only functions | **PASS** | No external libc symbols used; entry is `main(void)`. |

**Summary:**  
- **In this repo:** Algorithm and demo C code are freestanding and safe (no libc, no unsupported APIs). UART is intentionally stubbed; no LiteX CSR or build assets.  
- **Outside this repo:** SoC target, firmware Makefile/linker/startup, and real UART implementation must be provided by the LiteX/firmware side and must follow the checklist above.

---

## 2) Evidence: no libc / unsafe usage in litex_port/

**Headers used (grep over litex_port/*.c, *.h):**

- `tinyformer.c`: `#include "tinyformer.h"` (and conditionally `"trained_weights.h"`).
- `tinyformer.h`: `#include <stdint.h>`.
- `main.c`: `#include <stdint.h>`, `"tinyformer.h"`.
- `demo_main.c`: `#include <stdint.h>`, `"tinyformer.h"`, `"demo_samples.h"`, `"demo_classifier.h"`.
- `demo_samples.h`, `demo_classifier.h`, `trained_weights.h`: `#include <stdint.h>` or `"tinyformer.h"`.
- `trained_weights.c`: `"tinyformer.h"`, `"trained_weights.h"`.
- `demo_classifier.c`, `demo_samples.c`: `#include <stdint.h>`, local header.

**No:** `stdio.h`, `stdlib.h`, `string.h`, `time.h`, or any `printf`, `malloc`, `free`, `fopen`, `memcpy`, `memset`, `time(`, `errno` in `litex_port/`.  
**Single mention:** `main.c` line 3 comment “no malloc, no printf” (documentation only).

---

## 3) Patch applied: optional LiteX UART integration

**Done in-repo:**

- **`uart_litex.c` / `uart_litex.h`** — Golden minimal UART: when `USE_LITEX_UART` is defined and `generated/csr.h` is available, implements `uart_write_char()` with `uart_txfull_read()` + `uart_rxtx_write()`. Otherwise compiles to a no-op stub.
- **`main.c`** and **`demo_main.c`** — If `USE_LITEX_UART` is defined, they `#include "uart_litex.h"` and use the external `uart_write_char()`; otherwise they keep the local stub. No algorithm or libc changes.

**Firmware build:** Add `-DUSE_LITEX_UART`, `-I<litex_build>/software/include`, and link `uart_litex.c` when building for the FPGA. Omit these when building for host or without LiteX.

---

## 4) Where the “LiteX side” must be verified

These items cannot be verified inside TinyML_algo; your friend should confirm them in the LiteX/firmware repo:

1. **SoC target**  
   - e.g. `litex-boards/litex_boards/targets/nexys4ddr.py` (or a custom target that uses it).  
   - CPU: VexRiscv, RV32IM.  
   - Sys clk, memory map, and peripherals (including UART) come from this target and `generated/`.

2. **Firmware build**  
   - Makefile (or equivalent) that compiles all `litex_port/*.c` with:
     - `-ffreestanding -nostdlib`
     - `-march=rv32im -mabi=ilp32`
     - `-DUSE_TRAINED_WEIGHTS=1` for the demo
   - Linker script: `.text`/`.rodata`/`.data`/`.bss` in the SoC’s RAM region (BRAM or DDR as configured).
   - Startup (crt0): set stack pointer, clear `.bss`, copy `.data` if needed.

3. **UART**  
   - Include `generated/csr.h` (and any `generated/soc.h` or similar used by the target).  
   - Implement `uart_write_char()` with the LiteX UART CSR API (polling TX full, then write byte). See Section 5.

---

## 5) Golden minimal UART implementation (LiteX standard)

LiteX generates a CSR header (e.g. `build/nexys4ddr/software/include/generated/csr.h`) that provides:

- `uart_txfull_read()` — returns non-zero when TX FIFO is full.  
- `uart_rxtx_write(uint8_t x)` — writes one byte to the UART TX.

Standard polling pattern: wait until TX is not full, then write the character.

**Snippet to use in `main.c` and `demo_main.c`** (replace the stub body of `uart_write_char` when building with LiteX):

```c
#include <stdint.h>

/* When building with LiteX, include the generated CSR header, e.g.:
 * #include <generated/csr.h>
 * or add the build/include path and use: #include "csr.h"
 */

static void uart_write_char(char c)
{
#if defined(USE_LITEX_UART) && defined(CSR_UART_BASE)
    while (uart_txfull_read())
        ;
    uart_rxtx_write((uint8_t)c);
#else
    (void)c;   /* stub when not on LiteX */
#endif
}
```

**Build:**  
- Add compiler include path: `-I<litex_build>/software/include` (or where `generated/csr.h` lives).  
- Define `USE_LITEX_UART` when building for FPGA so this path is compiled.

**If the SoC uses a different UART name** (e.g. `serial`): the generated API is typically `serial_txfull_read()` and `serial_rxtx_write()`. Substitute that name in `uart_litex.c`; the pattern is the same.

**Interrupts:**  
For bare-metal, polling is the usual and recommended approach. If the firmware uses UART TX events, clear the event after writing and ensure `uart_ev_pending_write()` / enable semantics match the LiteX docs for the UART core.

**Drop-in module:** Use `litex_port/uart_litex.c` and `litex_port/uart_litex.h` when building with LiteX; see Section 3.

---

## 6) File reference summary

| Path | Purpose |
|------|--------|
| `litex_port/tinyformer.c` | TinyFormer encoder; `USE_TRAINED_WEIGHTS` selects weights. |
| `litex_port/tinyformer.h` | S, D, FFN, `tinyformer_encode()` API. |
| `litex_port/main.c` | Checksum demo; UART stub at 14–18. |
| `litex_port/demo_main.c` | UCI HAR demo; UART stub at 17–21. |
| `litex_port/trained_weights.c/h` | Int8 weights for encoder (used when `USE_TRAINED_WEIGHTS=1`). |
| `litex_port/demo_samples.c/h` | Demo input samples and labels. |
| `litex_port/demo_classifier.c/h` | Classifier head weights. |
| `litex_port/uart_litex.c` | Golden UART implementation (LiteX CSR); stub when not USE_LITEX_UART. |
| `litex_port/uart_litex.h` | Declares `uart_write_char(char c)` for LiteX build. |

No LiteX SoC target, no Makefile/linker/startup, no `csr.h` or `generated/` in this repo; those remain in the LiteX/firmware tree.
