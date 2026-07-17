# What this folder is (in simple words)

The OUTPUT of training (`training/train_tinyformer_uci_har.py`):

- `state_dict.pt` - the trained TinyFormer encoder weights (PyTorch, float).
- `classifier.npz` - the trained 6-class classifier head.

These float weights are the model's learned knowledge. `tools/export_weights.py` and
`training/export_and_make_fpga_demo.py` quantize them to int8 and turn them into the C
files the firmware compiles in (`trained_weights.c`, `demo_classifier.c`).
