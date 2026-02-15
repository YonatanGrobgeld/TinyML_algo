# TinyFormer + UCI HAR: Algorithm, Data, and Weights Brief

A concise reference for understanding and explaining this repo: what problem we solve, how data flows, how the model is built, how weights are quantized, what runs on FPGA, and common misunderstandings.

---

## 1. What problem we solve

- **UCI HAR** (Human Activity Recognition) is a standard dataset of smartphone inertial signals. Each sample is a short window of body acceleration and gyroscope (6 channels × 128 timesteps). The task is to classify the **activity** into one of **6 classes** (e.g. walking, walking upstairs, walking downstairs, sitting, standing, laying). Labels are **0..5**.
- **Input in the demo**: each sample is preprocessed to shape **[16, 32]** — 16 timesteps, 32 features per timestep — and quantized to **int8**. So the C code receives `int8_t input[16][32]`: 16 “tokens” of 32 dimensions each, already z-scored and scaled to int8 range.

---

## 2. Data pipeline (raw → processed)

- **Raw signals**: from UCI HAR we get 6 channels × 128 timesteps per sample:
  - body_acc_x, body_acc_y, body_acc_z
  - body_gyro_x, body_gyro_y, body_gyro_z  
  Stored as text files (one file per channel), loaded as float, stacked into **[N, 6, 128]**.

- **Downsampling**: time axis 128 → 16 by **average pooling** over non-overlapping chunks of 8. So we get **[N, 6, 16]** then reorder to **[N, 16, 6]** (16 steps, 6 raw channels per step).

- **32-D features per timestep**:
  - **0..5**: raw ax, ay, az, gx, gy, gz (after pooling).
  - **6**: accel magnitude √(ax²+ay²+az²).
  - **7**: gyro magnitude √(gx²+gy²+gz²).
  - **8..10**: delta accel (ax, ay, az) vs previous timestep; 0 at t=0.
  - **11..13**: delta gyro (gx, gy, gz) vs previous timestep; 0 at t=0.
  - **14..31**: zero padding (reserved).

- **Normalization**: z-score per feature using **train** mean and std (computed over all train samples and timesteps). The same train mean/std are applied to the test set (no test leakage).

- **Final tensors** (in `data/uci_har_processed/uci_har_processed.npz`):
  - `X_train`: **[N_train, 16, 32]** float32
  - `X_test`: **[N_test, 16, 32]** float32  
  - `y_train` / `y_test`: labels **0..5**.

---

## 3. Model architecture (TinyFormer)

We use a **single TinyFormer encoder block** plus a **simple classifier head**. One attention head only (no multi-head).

**Encoder block, in order:**

1. **Q/K/V projections**  
   Three linear layers: each token `x[16][32]` → Q, K, V with weight matrices **32×32** and biases **[32]**. So we have `W_q`, `W_k`, `W_v` (each [32][32]), `b_q`, `b_k`, `b_v`. Outputs: `q_buf`, `k_buf`, `v_buf` each [16][32] int8.

2. **Attention scores (streaming)**  
   For each query position `i`, we compute score with every key position `j`:  
   `score[i][j] = dot(Q[i], K[j])` then scale (right-shift to approximate ÷√D). We **do not** store a full 16×16 matrix: we compute one query at a time and reuse 1D buffers `scores[16]` and `exp_buf[16]`. That’s the “streaming” or “tiled” attention — same math, less RAM.

3. **Softmax approximation**  
   For each query: (a) subtract **max** over keys (numerical stability), (b) scale to a small integer range, (c) approximate exp with a **LUT** (16 entries for inputs roughly [-15, 0], values in Q10 fixed-point), (d) normalize so weights sum to 1 (Q15 fixed-point). No floating point.

4. **Weighted sum → attention output**  
   For each query `i`:  
   `context[i][d] = sum_j softmax_weight[i][j] * V[j][d]`.  
   Result is [16][32] int8 (after saturation).

5. **Output projection**  
   Linear: `W_o` [32][32], `b_o` [32]. Then **residual**: `attn_out = input + output_proj(context)` (saturated to int8).

6. **Feed-forward network (FFN)**  
   - First layer: `W_ff1` **[64][32]**, `b_ff1` [64] → ReLU → hidden [16][64].  
   - Second layer: `W_ff2` **[32][64]**, `b_ff2` [32] → output [16][32].  
   - **Residual**: final output = `attn_out + ffn_out`.

So: **one encoder block**, **one head**, **int8 everywhere** with **int32 accumulators** and shift/saturate back to int8.

---

## 4. Weights and quantization

**Encoder weights (in `trained_weights.c/h`):**

| Tensor   | Shape    | Role            |
|----------|----------|-----------------|
| W_q, W_k, W_v, W_o | [32][32] | Q/K/V and output projection |
| b_q, b_k, b_v, b_o | [32]     | Biases          |
| W_ff1    | [64][32] | FFN first layer |
| W_ff2    | [32][64] | FFN second layer|
| b_ff1    | [64]     | FFN bias 1      |
| b_ff2    | [32]     | FFN bias 2      |

**Export:** `tools/export_weights.py` loads a PyTorch `state_dict`, clips and rounds each tensor to **int8 in [-127, 127]**, and writes C **row-major** arrays (e.g. `W_q[TINYFORMER_D][TINYFORMER_D]`) so the C matvec loops match.

**What “int8 weights/activations, int32 accumulators” means:**  
- Dot products are computed in **int32** (sum of products of int8 values).  
- Results are then **scaled** (e.g. right-shift) and **saturated** to **int8** to stay in range. No floats on the FPGA.

**Classifier head (`demo_classifier.c/h`):**  
- **Mean pool** over the 16 encoder output tokens → one vector **[32]** int8.  
- **Linear layer**: `cls_W` [6][32], `cls_b` [6] → logits for 6 classes (in int32 in C).  
- Argmax over logits = predicted class 0..5.

---

## 5. What is actually running on FPGA

**On the FPGA (VexRiscv, bare-metal C):**

- **TinyFormer encoder**: `tinyformer_encode(input, output)` — one block, int8 in/out [16][32].
- **Classifier**: mean-pool encoder output → linear layer → argmax → predicted class.
- **Demo loop**: for each of a small number of **demo samples**, run encoder + classifier and **UART-print** something like `pred=X exp=Y` (predicted vs expected label).
- **UART**: polling-only `uart_write_char` (from `uart_litex.c` when built with LiteX).

**Not on FPGA:**

- **PyTorch training**: done on a host; we only export weights to C.
- **Preprocessing**: raw → [N,16,32], z-score, etc. is done in Python; the FPGA only sees **already quantized** int8 demo inputs stored in `demo_samples.c`.

**Demo samples:**  
A small set of **preselected test samples** (e.g. 10), quantized to int8 and stored as `demo_inputs[DEMO_NUM_SAMPLES][16][32]` and `demo_labels[DEMO_NUM_SAMPLES]`. Generated by `training/export_and_make_fpga_demo.py` from the processed NPZ and classifier.npz.

---

## 6. Common misunderstandings

- **“Is this a full transformer?”**  
  No. It’s **one** encoder block plus a **simple linear classifier head**. No decoder, no multi-head (we use 1 head), no stack of layers.

- **“Does it use floating point on the FPGA?”**  
  No. Everything is **fixed-point**: int8 weights and activations, int32 accumulators, right-shifts and saturation. Softmax uses an integer exp LUT and Q15-style normalization.

- **“Where does accuracy come from?”**  
  From **training in PyTorch** (floating point). The C code only **runs** the exported int8 weights; it doesn’t train. We accept a small accuracy drop from quantization.

- **“Is the 16×32 input the raw sensor data?”**  
  No. It’s **preprocessed**: downsampled 128→16, 32-D features per step (raw channels, magnitudes, deltas, padding), z-scored, then quantized to int8. Raw is 6×128 float.

---

## Pipeline (ASCII)

```
  Raw UCI HAR                Preprocess (Python)           Train (PyTorch)
  ─────────────               ───────────────────           ───────────────
  6 ch × 128 steps     →      [N,16,32] float               TinyFormer encoder
  (body acc/gyro)             z-score, 32-D features         + classifier head
                                                             state_dict.pt
                                                                   │
                                                                   ▼
  export_weights.py          export_and_make_fpga_demo.py
  ─────────────────         ─────────────────────────────
  state_dict.pt       →     trained_weights.c/h
  (encoder only)             demo_samples.c/h (int8 inputs + labels)
                             demo_classifier.c/h (6-class head)
                                   │
                                   ▼
  FPGA (C, bare-metal)
  ─────────────────
  tinyformer_encode()  →  mean_pool  →  classifier  →  UART "pred=X exp=Y"
  (int8 [16][32])         [32]         logits→argmax
```

---

## 10-line talk track (for a teammate)

1. We’re doing **human activity recognition** on the UCI HAR dataset: 6 classes from smartphone inertial data.
2. Raw data is **6 channels × 128 timesteps**; we **downsample to 16 steps** and build **32-D features** per step (raw, magnitudes, deltas, padding), then **z-score** with train statistics.
3. The model is a **single TinyFormer encoder block** (Q/K/V, one-head attention, output projection, residual, FFN with ReLU, residual) plus a **linear classifier** to 6 classes.
4. We use **int8 weights and activations** and **int32 accumulators**; no floats on the FPGA. Attention is **streaming** — we never store the full 16×16 score matrix.
5. **Softmax** is approximated with **max-subtraction** and an **integer exp LUT**, then Q15 fixed-point normalization.
6. **Weights** are trained in **PyTorch** and exported to C with `export_weights.py` (encoder) and the demo script (classifier + demo samples).
7. On the **FPGA** we only run: **encoder → mean-pool → classifier → argmax**, and print **pred vs expected** over UART for a few **preselected int8 demo samples**.
8. **Preprocessing and training** stay on the host; the board gets already quantized inputs and weights.
9. So: it’s **not** a full transformer — one block, one head — and it’s **fully fixed-point** in C.
10. Accuracy comes from **PyTorch training**; the C runtime just executes the exported int8 network.
