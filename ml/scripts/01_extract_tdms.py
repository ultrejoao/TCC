"""Extrai os 45 arquivos .tdms (corrente + temperatura) para ml/data/raw."""

import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import CURRENT_TEMP_ZIP, TDMS_DIR  # noqa: E402


def main() -> None:
    with zipfile.ZipFile(CURRENT_TEMP_ZIP) as z:
        infos = z.infolist()
        total = len(infos)
        for i, info in enumerate(infos, 1):
            dest = TDMS_DIR / info.filename
            if dest.exists() and dest.stat().st_size == info.file_size:
                print(f"[{i}/{total}] {info.filename} ja existe, pulando")
                continue
            z.extract(info, TDMS_DIR)
            print(f"[{i}/{total}] {info.filename} ({info.file_size/1e6:.1f} MB)", flush=True)
    print(f"\nOK -> {TDMS_DIR}")


if __name__ == "__main__":
    main()
