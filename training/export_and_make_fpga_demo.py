#!/usr/bin/env python3
"""
Export trained TinyFormer weights and generate FPGA demo samples.

This script:
  1) Runs tools/export_weights.py on artifacts/state_dict.pt to generate:
       - litex_port/trained_weights.h
       - litex_port/trained_weights.c
  2) Loads data/uci_har_processed/uci_har_processed.npz and selects a small set of test samples.
  3) Quantizes these samples to int8 using a global scale factor.
  4) Writes:
       - litex_port/demo_samples.h
       - litex_port/demo_samples.c
     containing:
       const int8_t  demo_inputs[DEMO_NUM_SAMPLES][16][32];
       const uint8_t demo_labels[DEMO_NUM_SAMPLES];
  5) Loads artifacts/classifier.npz and exports a simple classifier head:
       - litex_port/demo_classifier.h
       - litex_port/demo_classifier.c
     containing:
       const int8_t cls_W[6][32];
       const int8_t cls_b[6];
"""

import subprocess
from pathlib import Path

import numpy as np


S = 16
D = 32
N_CLASSES = 6
DEMO_NUM_SAMPLES = 10


def run_export_weights(repo_root: Path) -> None:
    ckpt = repo_root / "artifacts" / "state_dict.pt"
    if not ckpt.exists():
        raise FileNotFoundError(f"Checkpoint not found: {ckpt}")
    cmd = [
        "python3",
        str(repo_root / "tools" / "export_weights.py"),
        "--checkpoint",
        str(ckpt),
        "--output-dir",
        "litex_port",
    ]
    print("Running:", " ".join(cmd))
    subprocess.check_call(cmd, cwd=repo_root)


def select_demo_indices(y_test: np.ndarray) -> np.ndarray:
    """Select ~DEMO_NUM_SAMPLES test indices, attempting to cover all classes."""
    indices_per_class = {c: [] for c in range(N_CLASSES)}
    for idx, y in enumerate(y_test):
        if len(indices_per_class[y]) < 3:  # cap per class to avoid huge lists
            indices_per_class[y].append(idx)
    chosen = []
    # First, try to get at least one per class
    for c in range(N_CLASSES):
        if indices_per_class[c]:
            chosen.append(indices_per_class[c][0])
    # Fill up to DEMO_NUM_SAMPLES with remaining indices
    if len(chosen) < DEMO_NUM_SAMPLES:
        all_indices = list(range(len(y_test)))
        for idx in all_indices:
            if idx not in chosen:
                chosen.append(idx)
            if len(chosen) >= DEMO_NUM_SAMPLES:
                break
    return np.array(chosen[:DEMO_NUM_SAMPLES], dtype=np.int64)


def quantize_inputs(X: np.ndarray, scale: float = 32.0) -> np.ndarray:
    """
    Quantize normalized float inputs to int8 using a global scale factor.

    x_int8 = clip(round(x * scale), -127, 127)
    """
    Xq = np.clip(np.round(X * scale), -127.0, 127.0).astype(np.int8)
    return Xq


def write_demo_samples(repo_root: Path, X_demo_q: np.ndarray, y_demo: np.ndarray) -> None:
    litex_dir = repo_root / "litex_port"
    litex_dir.mkdir(parents=True, exist_ok=True)

    h_path = litex_dir / "demo_samples.h"
    c_path = litex_dir / "demo_samples.c"

    num = X_demo_q.shape[0]

    with h_path.open("w") as f:
        f.write(
            "#ifndef DEMO_SAMPLES_H\n"
            "#define DEMO_SAMPLES_H\n\n"
            "#include <stdint.h>\n\n"
            f"#define DEMO_NUM_SAMPLES {num}\n"
            f"#define DEMO_S 16\n"
            f"#define DEMO_D 32\n\n"
            "extern const int8_t  demo_inputs[DEMO_NUM_SAMPLES][DEMO_S][DEMO_D];\n"
            "extern const uint8_t demo_labels[DEMO_NUM_SAMPLES];\n\n"
            "#endif // DEMO_SAMPLES_H\n"
        )

    with c_path.open("w") as f:
        f.write(
            '#include <stdint.h>\n'
            '#include "demo_samples.h"\n\n'
        )

        # Inputs
        f.write("const int8_t demo_inputs[DEMO_NUM_SAMPLES][DEMO_S][DEMO_D] = {\n")
        for i in range(num):
            f.write("    {\n")
            for t in range(S):
                row = ", ".join(str(int(v)) for v in X_demo_q[i, t, :])
                f.write(f"        {{ {row} }},\n")
            f.write("    },\n")
        f.write("};\n\n")

        # Labels
        labels_str = ", ".join(str(int(v)) for v in y_demo)
        f.write(f"const uint8_t demo_labels[DEMO_NUM_SAMPLES] = {{ {labels_str} }};\n")


def quantize_classifier(W_cls: np.ndarray, b_cls: np.ndarray, scale: float = 32.0):
    """
    Quantize classifier weights and biases to int8.
    A simple symmetric scheme is used; the classifier in C will accumulate
    into int32 and use argmax on the raw scores.
    """
    Wq = np.clip(np.round(W_cls * scale), -127.0, 127.0).astype(np.int8)
    bq = np.clip(np.round(b_cls * scale), -127.0, 127.0).astype(np.int8)
    return Wq, bq


def write_demo_classifier(repo_root: Path, Wq: np.ndarray, bq: np.ndarray) -> None:
    litex_dir = repo_root / "litex_port"
    h_path = litex_dir / "demo_classifier.h"
    c_path = litex_dir / "demo_classifier.c"

    with h_path.open("w") as f:
        f.write(
            "#ifndef DEMO_CLASSIFIER_H\n"
            "#define DEMO_CLASSIFIER_H\n\n"
            "#include <stdint.h>\n\n"
            "#define DEMO_NUM_CLASSES 6\n"
            "#define DEMO_D 32\n\n"
            "extern const int8_t cls_W[DEMO_NUM_CLASSES][DEMO_D];\n"
            "extern const int8_t cls_b[DEMO_NUM_CLASSES];\n\n"
            "#endif // DEMO_CLASSIFIER_H\n"
        )

    with c_path.open("w") as f:
        f.write(
            '#include <stdint.h>\n'
            '#include "demo_classifier.h"\n\n'
        )

        # Weights
        f.write("const int8_t cls_W[DEMO_NUM_CLASSES][DEMO_D] = {\n")
        for c in range(Wq.shape[0]):
            row = ", ".join(str(int(v)) for v in Wq[c, :])
            f.write(f"    {{ {row} }},\n")
        f.write("};\n\n")

        # Biases
        b_str = ", ".join(str(int(v)) for v in bq)
        f.write(f"const int8_t cls_b[DEMO_NUM_CLASSES] = {{ {b_str} }};\n")


def main() -> None:
    repo_root = Path(__file__).resolve().parents[1]

    # 1) Export TinyFormer encoder weights to C.
    run_export_weights(repo_root)

    # 2) Load processed data and select demo samples.
    data_path = repo_root / "data" / "uci_har_processed" / "uci_har_processed.npz"
    data = np.load(data_path)
    X_test = data["X_test"].astype(np.float32)  # [N_test, 16, 32]
    y_test = data["y_test"].astype(np.int64)

    demo_idx = select_demo_indices(y_test)
    X_demo = X_test[demo_idx]
    y_demo = y_test[demo_idx]

    # 3) Quantize demo inputs.
    X_demo_q = quantize_inputs(X_demo, scale=32.0)
    write_demo_samples(repo_root, X_demo_q, y_demo)
    print("Wrote demo_samples.c/h")

    # 4) Export classifier head.
    clf_path = repo_root / "artifacts" / "classifier.npz"
    clf = np.load(clf_path)
    W_cls = clf["W_cls"]  # [6, 32]
    b_cls = clf["b_cls"]  # [6]

    Wq, bq = quantize_classifier(W_cls, b_cls, scale=32.0)
    write_demo_classifier(repo_root, Wq, bq)
    print("Wrote demo_classifier.c/h")


if __name__ == "__main__":
    main()

