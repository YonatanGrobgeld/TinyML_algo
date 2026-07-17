# Repository Guide — What Every Directory and File Is For

A plain-language map of the project. For the full technical story see
[REPORT_NOTES_IMPLEMENTATION.md](REPORT_NOTES_IMPLEMENTATION.md) and
[Docs/Project_Report.md](Docs/Project_Report.md).

**The project in one line:** a tiny Transformer (TinyFormer) classifies human activity
from motion sensors on a RISC-V soft CPU (VexRiscv + LiteX) on a Nexys4DDR FPGA;
three custom hardware accelerators (DOT8 instruction, EXP-LUT peripheral, GEMV
peripheral) speed inference up 4.82× (759 ms → 157.55 ms) with bit-identical results.

---

## Root files

| File | Purpose |
|---|---|
| `README.md` | Project overview + the practical bring-up playbook: exact files, build flags and include paths per mode, the correctness gate, troubleshooting table. |
| `REPORT_NOTES_IMPLEMENTATION.md` | The best single technical summary: algorithm, dataset, accelerators, verification, full performance results with cycle math, and reproduction steps. |
| `REPO_GUIDE.md` | This file — the map of the repository. |
| `run_gemv_xsim.tcl` / `run_lut_xsim.tcl` | Vivado Tcl scripts that compile and run the two RTL simulations (GEMV and EXP-LUT testbenches). |

---

## `litex_port/` — the firmware (the C code that runs on the FPGA's RISC-V CPU)

**Layout note:** the *canonical* sources live in `litex_port/common/` plus the six mode
directories. The `.c/.h` files sitting flat in `litex_port/` itself are an **older
flat-layout copy** kept for reference — when a filename exists in both places, the
`common/` version is the one the documented builds use.

### `litex_port/common/` — shared firmware sources (used by every build mode)

| File | Purpose |
|---|---|
| `tinyformer.c` | **The brain.** The full TinyFormer encoder in portable C: Q/K/V projections, streaming attention with fixed-point softmax, output projection + residual, 2-layer FFN + residual. Compile-time `USE_*_HW` macros switch each heavy step between pure software (baseline) and the hardware accelerators. |
| `tinyformer.h` | Public interface: model sizes (S=16, D=32, FFN=64) and `tinyformer_encode()`. |
| `demo_runner.c` | The demo loop: for each of 10 built-in samples, run the encoder, print the `ENC_CKSUM` correctness checksum, mean-pool, classify into 6 activities, print `pred`/`exp` over UART. |
| `demo_runner.h` | Declares `demo_run()` and `demo_print_banner()`. |
| `uart_litex.c/.h` | Minimal UART driver (how text reaches the PC over the serial cable). Auto-selects `uart_*` vs `serial_*` LiteX naming; compiles to stubs if no UART. |
| `trained_weights.c/.h` | The model's learned knowledge as int8 arrays — **auto-generated** from PyTorch training. |
| `demo_samples.c/.h` | 10 pre-quantized test recordings + their true labels — **auto-generated**. |
| `demo_classifier.c/.h` | The final 6-class linear classifier weights — **auto-generated**. |

### Mode directories — one tiny `main` per build configuration

| Directory | Build | Macros |
|---|---|---|
| `baseline/` | No accelerators (the 759 ms reference). Also contains the timer0 stopwatch code. | none |
| `accel_dot8/` | DOT8 custom instruction only | `USE_DOT8_HW` |
| `accel_lut/` | EXP-LUT peripheral only | `USE_EXP_LUT_HW` |
| `accel_gemv/` | GEMV peripheral only | `USE_GEMV_HW` |
| `accel_dot8_lut/` | DOT8 + LUT | both |
| `accel_all/` | All three — the 157.55 ms / 4.82× headline build; also measures with timer0. | all three |

Each mode's `main_*.c` prints its `MODE:` banner and calls the shared `demo_run()`.

### Self-tests (run on the board before benchmarking)

| File | Purpose |
|---|---|
| `tests_dot8.c/.h` | ~1000 random vectors: hardware DOT8 vs C reference → prints `DOT8 PASS`. |
| `tests_lut.c/.h` | All 16 LUT entries vs the golden table → prints `LUT PASS`. |
| `tests_gemv.c/.h` | Y = W·X on hardware vs C reference, all 4 shapes (32/64 × 32/64) → prints `GEMV self-test PASS`. |

### Build & platform glue

| File | Purpose |
|---|---|
| `Makefile`, `setup_build.sh` | How the firmware is compiled and linked. |
| `crt0.S` | First code after reset: stack, trap handler, jump to `main()`. |
| `linker.ld` | Memory map for the firmware image. |
| `isr.c` | Empty interrupt handler (the design polls; no interrupts). |
| `include/` | Minimal LiteX-style system headers (CSR access, irq, system) so the firmware compiles standalone. |
| `generated/` | **Sample** of the files LiteX auto-generates for the SoC (`csr.h` = the address book of all peripheral registers, `soc.h` = clock frequency, `mem.h`, linker fragments...). The real ones come from the separate LiteX SoC build tree. |
| `main.c`, `demo_main.c` + flat `.c/.h` copies | Older flat-layout versions kept for reference (see layout note above). |
| `firmware.elf` / `firmware.bin` | A prebuilt firmware binary. |
| `BUILD_INSTRUCTIONS.md`, `WINDOWS_INSTRUCTIONS.md`, `LITEX_FIRMWARE_REVIEW.md` | Build and integration notes. |

---

## `hw_extensions/` — the three hardware accelerators (RTL + LiteX glue + C drivers)

### `dot8/` — custom CPU instruction (4× int8 multiply-add in one cycle)

| File | Purpose |
|---|---|
| `Dot8Plugin.scala` | VexRiscv plugin: detects opcode `0x0B` / funct7 `0x01`, does 4 signed int8 multiplies + adder tree (4 DSP blocks) in the execute stage, writes the int32 result. |
| `sw/dot8.c/.h` | C driver: `dot8_pack()` + `dot8_4_lanes()`. Inline-asm `.insn` when `USE_DOT8_HW`, identical pure-C fallback otherwise. |
| `encoding.md`, `README.md` | Instruction encoding and rationale. |

### `exp_lut/` — softmax exponential lookup peripheral (killed the 71% bottleneck)

| File | Purpose |
|---|---|
| `exp_lut.v` | Verilog: 16 precomputed exp(0)..exp(−15) values in Q10 (1.0 = 1024), read combinationally. Matches the software table byte-for-byte. |
| `litex/exp_lut_periph.py` | LiteX/Migen glue: exposes an `index` (write) and `value` (read) register on the SoC bus. |
| `sw/exp_lut.c/.h` | Driver: `exp_lut_hw(idx)` — 2 bus operations (~12 cycles) vs ~21,000 cycles for the software exp; golden-table fallback when hardware is absent. |
| `exp_lut_spec.md`, `README.md` | Spec and register notes. |

### `gemv/` — matrix-vector engine peripheral (Y = W·X + b)

| File | Purpose |
|---|---|
| `rtl/gemv_core.v` | Verilog core (v2): packed 32-bit X/W memories (4 int8 per bus write → 4× less bus traffic), 4-lane MAC per clock (`dot4` → 4× less compute), 3-state FSM (IDLE → COMPUTE → DONE). 32×32 matvec in ~256 compute cycles. |
| `litex/gemv_periph.py` | LiteX glue: the 7 CSR registers (CTRL, X_IN, W_IN, B_IN, Y_OUT, STATUS, Y_NEXT) and the one-cycle start/clear_done pulses. |
| `sw/gemv.c/.h` | Driver: pack 4 values per write, stream X/W/b, start, poll done, read Y (writing `Y_NEXT` after each read to advance the pointer). |
| `gemv_spec.md`, `README.md` | Spec incl. register map and v1→v2 changes. |

### `sim/` — RTL simulation (run before touching the FPGA)

| File | Purpose |
|---|---|
| `tb_gemv.sv` | GEMV testbench: deterministic + randomized + int8-extremes tests, self-checking (`$fatal` on mismatch), dumps a waveform. |
| `tb_lut.sv` | LUT testbench: sweeps all 16 indices against `expected_lut.mem`. |
| `expected_lut.mem` | Golden LUT values for the testbench. |
| `Makefile`, `simulate.ps1`, `README_SIMULATION.md` | How to run the simulations. |

---

## `training/` — host-side pipeline (PyTorch on a PC; run in this order)

| File | Purpose |
|---|---|
| `download_uci_har.py` | Step 1: download the UCI HAR dataset (phone accelerometer/gyroscope recordings, 6 activities). |
| `preprocess_uci_har.py` | Step 2: reshape raw data to what TinyFormer expects — 128→16 timesteps, 32 features per step (zero-padded so D is a multiple of 4 for the hardware), z-score normalize. Output: `[N,16,32]` arrays. |
| `train_tinyformer_uci_har.py` | Step 3: train the TinyFormer + 6-class head in PyTorch (float). Saves `artifacts/state_dict.pt` and `classifier.npz`. Also the accuracy reference for the int8 C version. |
| `export_and_make_fpga_demo.py` | Step 4: the PyTorch→C bridge — quantize weights and 10 demo samples to int8 and generate `trained_weights.c/h`, `demo_samples.c/h`, `demo_classifier.c/h`. |

## `tools/` and `scripts/` — export & measurement utilities

| File | Purpose |
|---|---|
| `tools/export_weights.py` | The quantizer: float weights → clipped symmetric int8 C arrays in the exact layout `tinyformer.c` expects. |
| `tools/uart_sniff.py` | Debug: passively show every byte the board sends. |
| `scripts/run_baseline_and_measure.py` | Measurement: trigger runs over serial, parse `ENC_CKSUM`/`CYCLES`/`TIME_US`, write CSV. The firmware's hardware timer is the authoritative number. |
| `scripts/uart_diagnose.py` | Debug: exercise the serial link to diagnose communication problems. |

---

## `data/` and `artifacts/` — datasets and trained weights

| Path | Purpose |
|---|---|
| `data/uci_har_raw/` | The original UCI HAR dataset (raw sensor recordings + labels). |
| `data/uci_har_processed/uci_har_processed.npz` | The preprocessed `[N,16,32]` tensors used for training. |
| `artifacts/state_dict.pt` | Trained encoder weights (PyTorch, float). |
| `artifacts/classifier.npz` | Trained 6-class classifier head. |

(Each has an `ABOUT_THIS_FOLDER.md` with more detail.)

---

## `Docs/` — the project report and figures

| Path | Purpose |
|---|---|
| `Project_Report.md` / `.docx` | The full formal report (theory, implementation, simulation, results, conclusions; Appendix A = LUT values, Appendix B = GEMV register map). |
| `figures/` | Figures 1–8 (system diagram, SoC architecture, DOT8 pipeline, LUT interface, GEMV dataflow, encoder architecture, cycle breakdown, latency comparison) + editable draw.io sources. |
| `waveforms/` | Simulation waveform screenshots (GEMV and LUT) with description docs. |
| `gen_diagrams.py`, `gen_figures_png.py`, `md_to_docx.py`, `restructure.py` | Helper scripts that produced the figures and the .docx. |

---

## `pulp-transformer/` — the upstream research code (reference only)

A copy of the academic PULP-Transformer kernels (Jung et al., *Optimizing the Deployment
of Tiny Transformers on Low-Power MCUs*, arXiv:2404.02945), targeting GAP9/ARM MCUs —
**not** our FPGA. It is the intellectual starting point (e.g. streaming attention that
never materializes the S×S matrix); our implementation is a clean rewrite in
`litex_port/common/tinyformer.c`. Nothing here is compiled into our firmware.
See `pulp-transformer/ABOUT_THIS_FOLDER.md`.

## `.agent/` — working notes

Internal analysis notes and comparisons (e.g. vs the KWT-Tiny paper) plus a firmware
build workflow. Useful background; the authoritative documents are the README, the
report, and REPORT_NOTES_IMPLEMENTATION.md.
