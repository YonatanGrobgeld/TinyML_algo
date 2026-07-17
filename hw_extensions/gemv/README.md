# Extension #3: GEMV (Matrix–Vector) Accelerator

## What GEMV is and how it fits TinyFormer

**GEMV** (general matrix–vector multiply) computes **Y = W × X + b**:
- **W**: `OUT_DIM × LEN` matrix (int8)
- **X**: vector of length `LEN` (int8)
- **b**: optional bias vector of length `OUT_DIM` (int32)
- **Y**: output vector of length `OUT_DIM` (int32)

In TinyFormer (`litex_port/tinyformer.c`), almost every layer is a matrix–vector product:
- **Q/K/V/O projections:** (32×32) × (32)
- **FFN layer 1:** (64×32) × (32)
- **FFN layer 2:** (32×64) × (64)

A dedicated GEMV accelerator offloads these inner loops from the CPU: the CPU streams in X and W (and optionally b), starts the core, then reads back Y. Requantization/saturation to int8 is left to software (or a future hardware block).

## v1 design (historical)

- **Memory model:** **CSR-fed** — the CPU writes X and W (one int8 byte per CSR write), then reads Y via MMIO.
- **Compute:** Sequential — one signed int8 multiply-accumulate per cycle. A 32×32 matvec ran for 1024 cycles on the HW side, but the bus push (~1088 MMIO writes per matvec) dominated wall time.
- **Supported sizes:** `LEN` and `OUT_DIM` each 32 or 64.
- **Control:** Polling only; software waits on a *done* status bit before reading Y.

## v2 design (current — implemented this commit)

Two changes versus v1:

1. **32-bit packed data path.** `X_IN` and `W_IN` were widened from 8-bit to 32-bit; the C driver packs four signed int8 lanes per CSR write using a small helper:

   ```c
   static inline uint32_t pack4_i8(const int8_t *p) {
       return  ((uint32_t)(uint8_t)p[0])
            | (((uint32_t)(uint8_t)p[1]) << 8)
            | (((uint32_t)(uint8_t)p[2]) << 16)
            | (((uint32_t)(uint8_t)p[3]) << 24);
   }
   ```

   For a 32×32 matvec this drops the X-load+W-load count from `32 + 1024 = 1056` CSR writes to `8 + 256 = 264`. The CPU↔GEMV bus is the v1 bottleneck, so this 4× reduction is most of the v2 win.

2. **4-lane parallel signed-int8 MAC.** Inside `gemv_core.v`, the int8 X and W RAMs are restructured as 32-bit-wide word memories (`x_mem [0:MAX_LEN/4-1]`, `w_mem [0:(MAX_OUT*MAX_LEN)/4-1]`), and the FSM does four signed `int8×int8` multiplies in parallel each cycle, summed via a 4-input adder tree into the accumulator. A 32×32 matvec is **256 hardware cycles** instead of 1024.

The `W_ADDR_BITS` parameter is also reduced from 12 (4096-byte addressing) to 10 (1024-word addressing), since the weight memory is now word-addressed.

**Measured impact** (full TinyFormer inference, including non-GEMV work):
- v1 byte-wide GEMV (with DOT8 + EXP_LUT): **190.67 ms** = 19.07 M cycles per inference
- v2 packed GEMV (with DOT8 + EXP_LUT): **157.55 ms** = 15.76 M cycles per inference

The 21 % v1→v2 improvement comes entirely from this peripheral; the v2 GEMV core uses **4 DSP blocks** for the parallel multiply, matched by the **4 DSP blocks** already used by the VexRiscv DOT8 plugin for a total of 8 DSPs in the SoC.

**Vivado timing.** The earlier single-cycle core (fetch → 4-lane multiply → accumulate in one clock) did not close timing at 100 MHz (WNS ≈ −6.3 ns). The current **v3** core pipelines that path into three stages (fetch → multiply → accumulate) and registers the memory reads, so it **meets timing at 100 MHz**: WNS = **+0.019 ns** post-route (all constraints met, 0 failing endpoints), with bit-identical `ENC_CKSUM` versus baseline.

## Future v3 ideas

- **DMA / bus-master.** Even with 32-bit packed loads, the CPU still spends ~270 MMIO writes per 32×32 matvec. A DMA-mode GEMV that fetches W from main RAM itself would eliminate the bus push entirely — expected ~10× more speedup over v2 on the matvec path alone.
- **Pipeline the dot4 sum.** Register the four `int8×int8` multiplies separately so the adder tree runs in its own cycle; closes timing at 100 MHz at the cost of one cycle of pipeline latency per MAC.
- **Requantize in hardware.** Add a block that saturates int32 Y to int8 (e.g. shift + clip) so the CPU receives ready-to-use activations without an extra software pass.
- **Preload weights.** Keep W resident across calls when a layer is reused (e.g. self-attention's same projection used for all 16 tokens).

## Directory layout

```
hw_extensions/gemv/
├── README.md           (this file)
├── gemv_spec.md        Register map, data formats, calling sequence
├── rtl/
│   └── gemv_core.v     RTL core (FSM, internal RAMs, sequential compute)
├── litex/
│   └── gemv_periph.py  LiteX CSR wrapper (pulses for start/clear_done; Y_NEXT for read advance)
└── sw/
    ├── gemv.h          C driver API
    └── gemv.c          C driver implementation (polling; both LiteX CSR and raw MMIO)
```

## CSR summary (v2 — see gemv_spec.md for full map)

| Offset | Name    | Width | R/W | Description |
|--------|---------|-------|-----|-------------|
| 0x00   | CTRL    | 8     | R/W | start (pulse), clear_done (pulse), len_64, out_dim_64, enable_bias |
| 0x04   | X_IN    | **32** | W   | **4 packed int8 lanes per write** (LSB = lane 0). LEN/4 writes per X. |
| 0x08   | W_IN    | **32** | W   | **4 packed int8 lanes per write** (LSB = lane 0). OUT_DIM·LEN/4 writes per W. |
| 0x0C   | B_IN    | 32    | W   | Stream int32 bias (optional) |
| 0x10   | Y_OUT   | 32    | R   | Read current Y[i] (does not advance) |
| 0x14   | STATUS  | 8     | R   | busy (bit 0), done (bit 1) |
| 0x18   | Y_NEXT  | 8     | W   | Write to advance Y read pointer (pulse) |

**Software sequence:** clear_done pulse → `gemv_load_x()` (packs 4 lanes per write) → `gemv_load_w()` (packs 4 lanes per write) → optional `gemv_load_b()` → `gemv_start()` (config + start pulse) → poll done → for each i: read Y_OUT, write Y_NEXT → clear_done before next run.

**Compatibility.** The v2 hardware requires the v2 driver: any byte-wide `gemv_x_in_write(byte)` from the v1 driver would only fill the bottom 8 bits and leave bytes 1-3 as zeros, corrupting the input vector. The two versions are not register-compatible.

## On-target self-test

- **`litex_port/tests_gemv.c`** and **`litex_port/tests_gemv.h`** implement a minimal self-test:
  - Software reference GEMV (int8×int8→int32) with deterministic LCG inputs.
  - Runs HW GEMV for (32×32), (64×32), (32×64), (64×64); compares all Y elements.
  - **`int test_gemv(void);`** returns 0 on PASS, nonzero on FAIL; prints "GEMV self-test PASS" or "FAIL len=... i=... ref=... hw=..." via UART (no printf).
- **How to build:** Compile `tests_gemv.c`, `gemv.c`, and your UART source (e.g. `uart_litex.c`); link with `gemv.h`, `tests_gemv.h`. Define `GEMV_USE_LITEX_CSR` or `GEMV_BASE` as for the driver. From your firmware `main()`, call `gemv_init(base)` (if using MMIO base) then `test_gemv()`; non-zero return = fail.

## Integration status

- **Not yet wired** into any LiteX SoC target. Add `gemv_periph.py` and `rtl/gemv_core.v` to your SoC; link `gemv.c` and optionally `tests_gemv.c` in firmware. Run `test_gemv()` before integrating into TinyFormer.
