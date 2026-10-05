"""Download BIRD Mini-Dev (SQLite) and the HotpotQA distractor dev set into data/.

Run from the repository root:  python -m pipelines.download_data
The raw data is ignored by git (see .gitignore); only the sampled files are committed.
"""
import json
import urllib.request
import zipfile
from pathlib import Path

BIRD_URL = "https://bird-bench.oss-cn-beijing.aliyuncs.com/minidev.zip"
BIRD_DIR = Path("data/bird")
HOTPOT_FILE = Path("data/hotpot/hotpot_dev_distractor_v1.json")


def download_bird():
    if (BIRD_DIR / "minidev" / "MINIDEV" / "mini_dev_sqlite.json").exists():
        print("BIRD already downloaded")
        return
    BIRD_DIR.mkdir(parents=True, exist_ok=True)
    zip_path = Path("minidev.zip")
    print("Downloading BIRD Mini-Dev (about 760 MB)...")
    urllib.request.urlretrieve(BIRD_URL, zip_path)
    with zipfile.ZipFile(zip_path) as z:
        z.extractall(BIRD_DIR)
    zip_path.unlink()
    print("BIRD ready in", BIRD_DIR)


def download_hotpot():
    # The original CMU host was unreachable when we tried it, so we use the
    # Hugging Face copy of the same dataset. Its ID field is "id", not "_id".
    if HOTPOT_FILE.exists():
        print("HotpotQA already downloaded")
        return
    from datasets import load_dataset

    HOTPOT_FILE.parent.mkdir(parents=True, exist_ok=True)
    ds = load_dataset("hotpotqa/hotpot_qa", "distractor", split="validation")
    json.dump([dict(x) for x in ds], open(HOTPOT_FILE, "w"))
    print("HotpotQA ready:", len(ds), "questions")


if __name__ == "__main__":
    download_bird()
    download_hotpot()
