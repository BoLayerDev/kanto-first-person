#!/usr/bin/env python3
"""Generate and verify the locked KFP panorama quality variants."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import struct
import tempfile


ROOT = Path(__file__).resolve().parents[1]
HORIZON_DIR = ROOT / "assets" / "legacy" / "horizons"
INVENTORY_PATH = ROOT / "docs" / "legacy-panorama-inventory.json"
SOURCE_FILES = (
    "backdrop.png",
    "backdrop2.png",
    "backdrop3.png",
    "backdrop4.png",
)
SOURCE_SHA256 = {
    "backdrop.png": "3617b1bd09d9db3b2649c766ab8f7aadc884bdf2c51d5988f541ba12023d0603",
    "backdrop2.png": "238d0416dc42b4f5cd52f19860a79328cdf74673e12f7eb1082805c07db8402e",
    "backdrop3.png": "f7a8f8d4d4f78b7bef39d4ec392badf564e6cbea2d43dd6b336a0593dfcd7b4b",
    "backdrop4.png": "f276668b609b9828476858951e8a3d1843af025f5f58da79cb2ded29df4b560a",
}
QUALITY_WIDTHS = {"HIGH": 4096, "BALANCED": 2048, "LOW": 1024}
SOURCE_SIZE = (4096, 256)
PINNED_PILLOW_VERSION = "12.1.0"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def png_size(path: Path) -> tuple[int, int]:
    with path.open("rb") as handle:
        header = handle.read(24)
    if len(header) != 24 or header[:8] != b"\x89PNG\r\n\x1a\n":
        raise RuntimeError(f"not a PNG file: {path}")
    if header[12:16] != b"IHDR":
        raise RuntimeError(f"PNG has no leading IHDR chunk: {path}")
    return struct.unpack(">II", header[16:24])


def derived_name(source_name: str, width: int) -> str:
    source = Path(source_name)
    return f"{source.stem}-{width}{source.suffix}"


def expected_records() -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    for source_name in SOURCE_FILES:
        source_path = HORIZON_DIR / source_name
        records.append(
            {
                "path": source_path.relative_to(ROOT).as_posix(),
                "quality": "HIGH",
                "width": SOURCE_SIZE[0],
                "height": SOURCE_SIZE[1],
                "sha256": sha256(source_path),
                "derived_from": None,
            }
        )
        for quality in ("BALANCED", "LOW"):
            width = QUALITY_WIDTHS[quality]
            path = HORIZON_DIR / derived_name(source_name, width)
            records.append(
                {
                    "path": path.relative_to(ROOT).as_posix(),
                    "quality": quality,
                    "width": width,
                    "height": SOURCE_SIZE[1] * width // SOURCE_SIZE[0],
                    "sha256": sha256(path),
                    "derived_from": source_path.relative_to(ROOT).as_posix(),
                }
            )
    return records


def validate_sources() -> None:
    for name in SOURCE_FILES:
        path = HORIZON_DIR / name
        if png_size(path) != SOURCE_SIZE:
            raise RuntimeError(f"source panorama dimensions changed: {name}")
        if sha256(path) != SOURCE_SHA256[name]:
            raise RuntimeError(f"source panorama hash changed: {name}")


def generate() -> None:
    try:
        import PIL
        from PIL import Image
    except ImportError as error:
        raise RuntimeError("generation needs Pillow 12.1.0") from error

    if PIL.__version__ != PINNED_PILLOW_VERSION:
        raise RuntimeError(
            f"generation needs Pillow {PINNED_PILLOW_VERSION}; found {PIL.__version__}"
        )
    validate_sources()

    for source_name in SOURCE_FILES:
        source_path = HORIZON_DIR / source_name
        with Image.open(source_path) as source:
            if source.mode != "RGBA":
                raise RuntimeError(f"source panorama is not RGBA: {source_name}")
            for quality in ("BALANCED", "LOW"):
                width = QUALITY_WIDTHS[quality]
                size = (width, SOURCE_SIZE[1] * width // SOURCE_SIZE[0])
                output = HORIZON_DIR / derived_name(source_name, width)
                resized = source.resize(size, Image.Resampling.LANCZOS)
                with tempfile.NamedTemporaryFile(
                    prefix=output.name + ".", suffix=".tmp", dir=HORIZON_DIR,
                    delete=False,
                ) as temporary:
                    temporary_path = Path(temporary.name)
                try:
                    resized.save(
                        temporary_path,
                        format="PNG",
                        optimize=False,
                        compress_level=9,
                    )
                    os.replace(temporary_path, output)
                finally:
                    temporary_path.unlink(missing_ok=True)

    inventory = {
        "schema": 1,
        "scope": "public legacy panorama inventory",
        "generation": {
            "tool": "tools/generate_panorama_variants.py",
            "pillow_version": PINNED_PILLOW_VERSION,
            "resampling": "LANCZOS",
            "png_optimize": False,
            "png_compress_level": 9,
        },
        "quality_widths": QUALITY_WIDTHS,
        "files": expected_records(),
    }
    INVENTORY_PATH.write_text(
        json.dumps(inventory, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def check() -> None:
    validate_sources()
    try:
        inventory = json.loads(INVENTORY_PATH.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise RuntimeError("public panorama inventory is missing or invalid") from error
    if inventory.get("schema") != 1:
        raise RuntimeError("public panorama inventory schema is invalid")
    if inventory.get("quality_widths") != QUALITY_WIDTHS:
        raise RuntimeError("public panorama quality widths changed")
    if inventory.get("files") != expected_records():
        raise RuntimeError("public panorama inventory does not match packaged files")
    for record in inventory["files"]:
        path = ROOT / record["path"]
        if png_size(path) != (record["width"], record["height"]):
            raise RuntimeError(f"panorama dimensions do not match inventory: {record['path']}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "action", choices=("generate", "check"), nargs="?", default="check"
    )
    args = parser.parse_args()
    if args.action == "generate":
        generate()
    check()
    print("panorama variants verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
