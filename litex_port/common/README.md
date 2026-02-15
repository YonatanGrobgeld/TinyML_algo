# Common — shared TinyFormer and demo code

This directory holds the **shared algorithm and support code** used by all baseline and hardware-accelerated builds:

- **tinyformer.c / tinyformer.h** — TinyFormer encoder (single block, S=16, D=32).
- **demo_samples.c / demo_samples.h** — Pre-quantized UCI HAR demo inputs and labels.
- **demo_classifier.c / demo_classifier.h** — Linear classifier head weights.
- **demo_runner.c / demo_runner.h** — Shared demo flow: load samples, `tinyformer_encode()`, mean-pool, classify, print `pred=X exp=Y`.
- **uart_litex.c / uart_litex.h** — LiteX UART driver (or stub when `USE_LITEX_UART` is not defined).
- **trained_weights.c / trained_weights.h** — Trained encoder weights (used when `USE_TRAINED_WEIGHTS=1`).

There is **no duplication** of TinyFormer logic. Each variant (`baseline/`, `accel_dot8/`, etc.) compiles with the appropriate feature macros and links this common code.

Builds must add `-I litex_port/common` and compile the needed `.c` files from here (and from the chosen `main_*.c` and any accelerator driver).
