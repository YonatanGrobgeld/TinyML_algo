#!/usr/bin/env python3
"""
Preprocess UCI HAR raw inertial signals into TinyFormer-ready tensors.

Input (from data/uci_har/UCI HAR Dataset/):
  - train/Inertial Signals/body_acc_{x,y,z}_train.txt
  - train/Inertial Signals/body_gyro_{x,y,z}_train.txt
  - test/Inertial Signals/body_acc_{x,y,z}_test.txt
  - test/Inertial Signals/body_gyro_{x,y,z}_test.txt

Each sample has 6 channels x 128 timesteps.

Output:
  data/uci_har_processed.npz containing:
    X_train: [N_train, 16, 32]
    y_train: [N_train] (labels 0..5)
    X_test : [N_test, 16, 32]
    y_test : [N_test]  (labels 0..5)

Per-timestep feature vector (D = 32):
  0..5   : ax, ay, az, gx, gy, gz
  6      : accel magnitude
  7      : gyro magnitude
  8..10  : delta accel (ax, ay, az) vs previous timestep (0 at t=0)
  11..13 : delta gyro  (gx, gy, gz) vs previous timestep (0 at t=0)
  14..31 : zero padding

Time axis is downsampled from 128 -> 16 using average pooling over 8-step chunks.
Features are z-scored using train mean/std (computed over all train samples and
timesteps, per feature) and the same normalization is applied to test.
"""

from pathlib import Path

import numpy as np


def load_inertial_set(base: Path, split: str):
    sig_dir = base / split / "Inertial Signals"
    fnames = [
        f"body_acc_x_{split}.txt",
        f"body_acc_y_{split}.txt",
        f"body_acc_z_{split}.txt",
        f"body_gyro_x_{split}.txt",
        f"body_gyro_y_{split}.txt",
        f"body_gyro_z_{split}.txt",
    ]
    signals = []
    for fname in fnames:
        path = sig_dir / fname
        arr = np.loadtxt(path, dtype=np.float32)
        signals.append(arr)  # [N, 128]
    # Stack into [N, 6, 128]
    stacked = np.stack(signals, axis=1)
    return stacked  # [N, 6, 128]


def downsample_and_features(raw: np.ndarray) -> np.ndarray:
    """
    raw: [N, 6, 128] -> [N, 16, 32]
    """
    N, C, T = raw.shape
    assert C == 6 and T == 128

    # Average pool time: 128 -> 16 (chunks of 8).
    pooled = raw.reshape(N, C, 16, 8).mean(axis=-1)  # [N, 6, 16]
    # Reorder to [N, 16, 6]
    pooled = np.transpose(pooled, (0, 2, 1))

    # Allocate features [N, 16, 32]
    feats = np.zeros((N, 16, 32), dtype=np.float32)

    # Raw channels
    ax = pooled[:, :, 0]
    ay = pooled[:, :, 1]
    az = pooled[:, :, 2]
    gx = pooled[:, :, 3]
    gy = pooled[:, :, 4]
    gz = pooled[:, :, 5]

    feats[:, :, 0] = ax
    feats[:, :, 1] = ay
    feats[:, :, 2] = az
    feats[:, :, 3] = gx
    feats[:, :, 4] = gy
    feats[:, :, 5] = gz

    # Magnitudes
    acc_mag = np.sqrt(ax * ax + ay * ay + az * az)
    gyro_mag = np.sqrt(gx * gx + gy * gy + gz * gz)
    feats[:, :, 6] = acc_mag
    feats[:, :, 7] = gyro_mag

    # Deltas (t - t-1), 0 at t=0
    delta_ax = np.zeros_like(ax)
    delta_ay = np.zeros_like(ay)
    delta_az = np.zeros_like(az)
    delta_gx = np.zeros_like(gx)
    delta_gy = np.zeros_like(gy)
    delta_gz = np.zeros_like(gz)

    delta_ax[:, 1:] = ax[:, 1:] - ax[:, :-1]
    delta_ay[:, 1:] = ay[:, 1:] - ay[:, :-1]
    delta_az[:, 1:] = az[:, 1:] - az[:, :-1]
    delta_gx[:, 1:] = gx[:, 1:] - gx[:, :-1]
    delta_gy[:, 1:] = gy[:, 1:] - gy[:, :-1]
    delta_gz[:, 1:] = gz[:, 1:] - gz[:, :-1]

    feats[:, :, 8] = delta_ax
    feats[:, :, 9] = delta_ay
    feats[:, :, 10] = delta_az
    feats[:, :, 11] = delta_gx
    feats[:, :, 12] = delta_gy
    feats[:, :, 13] = delta_gz

    # Remaining features 14..31 remain zero.
    return feats


def main() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    uci_root = repo_root / "data" / "uci_har" / "UCI HAR Dataset"

    train_raw = load_inertial_set(uci_root, "train")  # [N_train, 6, 128]
    test_raw = load_inertial_set(uci_root, "test")    # [N_test, 6, 128]

    X_train = downsample_and_features(train_raw)  # [N_train, 16, 32]
    X_test = downsample_and_features(test_raw)    # [N_test, 16, 32]

    # Load labels (1..6) and convert to 0..5
    y_train_path = uci_root / "train" / "y_train.txt"
    y_test_path = uci_root / "test" / "y_test.txt"
    y_train = np.loadtxt(y_train_path, dtype=np.int64) - 1
    y_test = np.loadtxt(y_test_path, dtype=np.int64) - 1

    assert X_train.shape[0] == y_train.shape[0]
    assert X_test.shape[0] == y_test.shape[0]

    # Normalize using train mean/std over all samples & timesteps, per feature.
    train_flat = X_train.reshape(-1, X_train.shape[-1])  # [N_train*16, 32]
    mean = train_flat.mean(axis=0, keepdims=True)
    std = train_flat.std(axis=0, keepdims=True)
    std[std < 1e-6] = 1.0

    X_train_norm = (X_train - mean) / std
    X_test_norm = (X_test - mean) / std

    out_path = repo_root / "data" / "uci_har_processed.npz"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        out_path,
        X_train=X_train_norm.astype(np.float32),
        y_train=y_train.astype(np.int64),
        X_test=X_test_norm.astype(np.float32),
        y_test=y_test.astype(np.int64),
        mean=mean.astype(np.float32),
        std=std.astype(np.float32),
    )
    print(f"Saved preprocessed data to {out_path}")
    print(f"Train shape: {X_train_norm.shape}, Test shape: {X_test_norm.shape}")


if __name__ == "__main__":
    main()

