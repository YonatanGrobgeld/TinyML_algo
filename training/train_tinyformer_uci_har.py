#!/usr/bin/env python3
"""
Train a TinyFormer-based classifier on UCI HAR (preprocessed) and export
weights compatible with litex_port/tinyformer.c and tools/export_weights.py.

Input:
  data/uci_har_processed/uci_har_processed.npz (see preprocess_uci_har.py)

Output:
  artifacts/state_dict.pt   -- contains ONLY the TinyFormer encoder weights with
                               keys: W_q, W_k, W_v, W_o, W_ff1, W_ff2,
                                     b_q, b_k, b_v, b_o, b_ff1, b_ff2
  artifacts/classifier.npz  -- classifier head weights:
                               W_cls [6, 32], b_cls [6]
"""

import os
import random
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, TensorDataset


S = 16
D = 32
FFN = 64
N_CLASSES = 6


def set_seed(seed: int = 42) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)


class TinyFormerEncoder(nn.Module):
    def __init__(self, d_model: int = D, ffn_dim: int = FFN):
        super().__init__()
        self.proj_q = nn.Linear(d_model, d_model, bias=True)
        self.proj_k = nn.Linear(d_model, d_model, bias=True)
        self.proj_v = nn.Linear(d_model, d_model, bias=True)
        self.proj_o = nn.Linear(d_model, d_model, bias=True)

        self.ffn1 = nn.Linear(d_model, ffn_dim, bias=True)
        self.ffn2 = nn.Linear(ffn_dim, d_model, bias=True)

        self.relu = nn.ReLU()

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        x: [B, S, D]
        Returns: [B, S, D]
        """
        B, S_, D_ = x.shape
        assert S_ == S and D_ == D

        # Projections
        q = self.proj_q(x)  # [B, S, D]
        k = self.proj_k(x)
        v = self.proj_v(x)

        # Scaled dot-product attention (single head)
        # Scores: [B, S, S]
        scale = D ** 0.5
        scores = torch.matmul(q, k.transpose(1, 2)) / scale
        attn = torch.softmax(scores, dim=-1)  # [B, S, S]
        context = torch.matmul(attn, v)      # [B, S, D]

        # Output projection + residual
        attn_out = self.proj_o(context)
        y = x + attn_out

        # FFN + residual
        h = self.relu(self.ffn1(y))
        f = self.ffn2(h)
        z = y + f
        return z


class TinyFormerHARModel(nn.Module):
    def __init__(self):
        super().__init__()
        self.encoder = TinyFormerEncoder(d_model=D, ffn_dim=FFN)
        self.classifier = nn.Linear(D, N_CLASSES, bias=True)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        x: [B, S, D]
        """
        z = self.encoder(x)          # [B, S, D]
        pooled = z.mean(dim=1)       # [B, D] mean-pool over time
        logits = self.classifier(pooled)
        return logits


def train_model():
    repo_root = Path(__file__).resolve().parents[1]
    data_path = repo_root / "data" / "uci_har_processed" / "uci_har_processed.npz"
    artifacts_dir = repo_root / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    data = np.load(data_path)
    X_train = data["X_train"].astype(np.float32)  # [N_train, 16, 32]
    y_train = data["y_train"].astype(np.int64)
    X_test = data["X_test"].astype(np.float32)
    y_test = data["y_test"].astype(np.int64)

    set_seed(42)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    train_ds = TensorDataset(
        torch.from_numpy(X_train), torch.from_numpy(y_train)
    )
    test_ds = TensorDataset(
        torch.from_numpy(X_test), torch.from_numpy(y_test)
    )

    train_loader = DataLoader(train_ds, batch_size=64, shuffle=True)
    test_loader = DataLoader(test_ds, batch_size=128, shuffle=False)

    model = TinyFormerHARModel().to(device)
    optimizer = optim.Adam(model.parameters(), lr=1e-3)
    criterion = nn.CrossEntropyLoss()

    epochs = 15
    for epoch in range(1, epochs + 1):
        model.train()
        total_loss = 0.0
        correct = 0
        total = 0
        for xb, yb in train_loader:
            xb = xb.to(device)
            yb = yb.to(device)

            optimizer.zero_grad()
            logits = model(xb)
            loss = criterion(logits, yb)
            loss.backward()
            optimizer.step()

            total_loss += float(loss.item()) * xb.size(0)
            preds = logits.argmax(dim=1)
            correct += (preds == yb).sum().item()
            total += xb.size(0)

        train_loss = total_loss / total
        train_acc = correct / total

        # Eval
        model.eval()
        correct_test = 0
        total_test = 0
        with torch.no_grad():
            for xb, yb in test_loader:
                xb = xb.to(device)
                yb = yb.to(device)
                logits = model(xb)
                preds = logits.argmax(dim=1)
                correct_test += (preds == yb).sum().item()
                total_test += xb.size(0)
        test_acc = correct_test / total_test

        print(f"Epoch {epoch}/{epochs} - loss {train_loss:.4f}, "
              f"train acc {train_acc:.3f}, test acc {test_acc:.3f}")

    # Export TinyFormer encoder weights in the exact layout required by C.
    enc = model.encoder
    state_to_export = {
        "W_q": enc.proj_q.weight.detach().cpu(),     # [32,32]
        "W_k": enc.proj_k.weight.detach().cpu(),
        "W_v": enc.proj_v.weight.detach().cpu(),
        "W_o": enc.proj_o.weight.detach().cpu(),
        "W_ff1": enc.ffn1.weight.detach().cpu(),     # [64,32]
        "W_ff2": enc.ffn2.weight.detach().cpu(),     # [32,64]
        "b_q": enc.proj_q.bias.detach().cpu(),       # [32]
        "b_k": enc.proj_k.bias.detach().cpu(),
        "b_v": enc.proj_v.bias.detach().cpu(),
        "b_o": enc.proj_o.bias.detach().cpu(),
        "b_ff1": enc.ffn1.bias.detach().cpu(),       # [64]
        "b_ff2": enc.ffn2.bias.detach().cpu(),       # [32]
    }

    torch.save(state_to_export, artifacts_dir / "state_dict.pt")
    print(f"Saved TinyFormer encoder weights to {artifacts_dir/'state_dict.pt'}")

    # Export classifier head weights separately for FPGA demo.
    cls_W = model.classifier.weight.detach().cpu().numpy()  # [6, 32]
    cls_b = model.classifier.bias.detach().cpu().numpy()    # [6]
    np.savez(artifacts_dir / "classifier.npz", W_cls=cls_W, b_cls=cls_b)
    print(f"Saved classifier head weights to {artifacts_dir/'classifier.npz'}")


if __name__ == "__main__":
    train_model()

