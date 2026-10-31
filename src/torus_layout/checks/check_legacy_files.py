"""記録済みの既存ソースと設定を、実行開始時の内容と比較する。"""

import hashlib
import json
from pathlib import Path


def check_legacy_files() -> None:
    root = Path(__file__).resolve().parents[3]
    manifest = (
        Path(__file__).resolve().parents[1] / "tests/fixtures/protected_files.json"
    )
    records: dict[str, str] = json.loads(manifest.read_text())
    changed = [
        name
        for name, expected in records.items()
        if not (root / name).exists()
        or hashlib.sha256((root / name).read_bytes()).hexdigest() != expected
    ]
    if changed:
        raise RuntimeError(f"Protected files changed: {changed}")
    print(f"{len(records)} protected source/configuration files unchanged")


if __name__ == "__main__":
    check_legacy_files()
