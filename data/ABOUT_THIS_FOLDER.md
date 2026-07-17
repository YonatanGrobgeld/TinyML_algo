# What this folder is (in simple words)

- `uci_har_raw/` - the ORIGINAL UCI Human Activity Recognition dataset: phone accelerometer
  and gyroscope recordings of 30 people doing 6 activities (walking, stairs up/down,
  sitting, standing, laying). Downloaded by `training/download_uci_har.py`.
- `uci_har_processed/uci_har_processed.npz` - the same data after
  `training/preprocess_uci_har.py` reshaped it to what TinyFormer expects:
  [N samples, 16 timesteps, 32 features], normalized, labels 0-5.

This is the raw material the model was trained on. The 10 demo samples burned into the
firmware (`demo_samples.c`) were taken from the test split of this data.
