#!/usr/bin/env python3
"""
Download the UCI HAR Dataset (raw IMU signals) into data/uci_har_raw/.

This script fetches the original zip archive from the UCI repository,
extracts it under:

  data/uci_har/UCI HAR Dataset/

and prints a short summary of the number of train/test samples based on
the y_train.txt / y_test.txt label files.
"""

import os
import zipfile
from pathlib import Path
from urllib.request import urlretrieve


UCI_HAR_URL = (
    "https://archive.ics.uci.edu/ml/machine-learning-databases/"
    "00240/UCI%20HAR%20Dataset.zip"
)


def main() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    data_dir = repo_root / "data" / "uci_har_raw"
    data_dir.mkdir(parents=True, exist_ok=True)

    zip_path = data_dir / "UCI_HAR_Dataset.zip"
    if not zip_path.exists():
        print(f"Downloading UCI HAR Dataset to {zip_path} ...")
        urlretrieve(UCI_HAR_URL, zip_path)
        print("Download complete.")
    else:
        print(f"Zip already exists at {zip_path}, skipping download.")

    extract_dir = data_dir
    uci_root = extract_dir / "UCI HAR Dataset"

    if not uci_root.exists():
        print(f"Extracting {zip_path} into {extract_dir} ...")
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(extract_dir)
        print("Extraction complete.")
    else:
        print(f"{uci_root} already exists, skipping extraction.")

    # Sanity summary: count train/test samples from label files.
    y_train_path = uci_root / "train" / "y_train.txt"
    y_test_path = uci_root / "test" / "y_test.txt"

    if y_train_path.exists() and y_test_path.exists():
        with y_train_path.open("r") as f:
            n_train = sum(1 for _ in f)
        with y_test_path.open("r") as f:
            n_test = sum(1 for _ in f)
        print(f"UCI HAR: {n_train} train samples, {n_test} test samples.")
    else:
        print("Warning: could not find y_train.txt / y_test.txt for summary.")


if __name__ == "__main__":
    main()

