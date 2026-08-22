#!/usr/bin/env python3
"""Generate and verify the deterministic KFP cloud coverage textures."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import struct


ROOT = Path(__file__).resolve().parents[1]
SKY_DIR = ROOT / "assets" / "legacy" / "sky"
INVENTORY_PATH = ROOT / "docs" / "legacy-sky-inventory.json"
PINNED_PILLOW_VERSION = "12.1.0"
SIZE = 128
LATTICE = 16
LAYERS = (
    {"layer": 1, "seed": 11, "cut": 0.60, "file": "clouds-1.png"},
    {"layer": 2, "seed": 29, "cut": 0.66, "file": "clouds-2.png"},
    {"layer": 3, "seed": 47, "cut": 0.72, "file": "clouds-3.png"},
)
BAYER_4 = (
    (0, 8, 2, 10),
    (12, 4, 14, 6),
    (3, 11, 1, 9),
    (15, 7, 13, 5),
)


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


def units(seed: int, count: int) -> list[float]:
    state = seed
    values: list[float] = []
    for _ in range(count):
        state = state * 48271 % 2147483647
        values.append(state / 2147483647)
    return values


def smooth(lattice: list[float], x: int, y: int, cycles: int) -> float:
    # Integer cycle counts make the periodic lattice continuous where the PNG
    # wraps from its final texel to its first texel.
    fx, fy = x * cycles / SIZE, y * cycles / SIZE
    x0, y0 = int(fx // 1), int(fy // 1)
    tx, ty = fx - x0, fy - y0
    tx = tx * tx * (3 - 2 * tx)
    ty = ty * ty * (3 - 2 * ty)

    def value(px: int, py: int) -> float:
        return lattice[(py % cycles) * LATTICE + (px % cycles)]

    top = value(x0, y0) + (value(x0 + 1, y0) - value(x0, y0)) * tx
    bottom = value(x0, y0 + 1) + (
        value(x0 + 1, y0 + 1) - value(x0, y0 + 1)
    ) * tx
    return top + (bottom - top) * ty


def ordered_alpha(x: int, y: int, coverage: float) -> int:
    threshold = (BAYER_4[y % 4][x % 4] + 0.5) / 16
    return 255 if coverage >= threshold else 0


def pixels(seed: int, cut: float) -> list[tuple[int, int, int, int]]:
    lattice = units(seed, LATTICE * LATTICE)
    out: list[tuple[int, int, int, int]] = []
    for y in range(SIZE):
        for x in range(SIZE):
            sx, sy = x // 4 * 4, y // 4 * 4
            noise = (
                smooth(lattice, sx, sy, 2) * 0.6
                + smooth(lattice, sx, sy, 4) * 0.3
                + smooth(lattice, sx, sy, 8) * 0.1
            )
            coverage, shade = 0.0, 255
            if noise > cut:
                coverage, shade = 0.92, 255
            elif noise > cut - 0.07:
                coverage, shade = 0.72, 224
            elif noise > cut - 0.12:
                coverage, shade = 0.35, 204
            out.append((shade, shade, shade, ordered_alpha(x, y, coverage)))
    return out


def expected_records() -> list[dict[str, object]]:
    return [
        {
            "path": (SKY_DIR / str(layer["file"])).relative_to(ROOT).as_posix(),
            "layer": layer["layer"],
            "seed": layer["seed"],
            "cut": layer["cut"],
            "width": SIZE,
            "height": SIZE,
            "sha256": sha256(SKY_DIR / str(layer["file"])),
            "alpha": "binary ordered coverage",
        }
        for layer in LAYERS
    ]


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

    SKY_DIR.mkdir(parents=True, exist_ok=True)
    for layer in LAYERS:
        image = Image.new("RGBA", (SIZE, SIZE))
        image.putdata(pixels(int(layer["seed"]), float(layer["cut"])))
        image.save(
            SKY_DIR / str(layer["file"]),
            format="PNG",
            optimize=False,
            compress_level=9,
        )

    inventory = {
        "schema": 1,
        "scope": "public legacy-derived sky texture inventory",
        "generation": {
            "tool": "tools/generate_cloud_textures.py",
            "pillow_version": PINNED_PILLOW_VERSION,
            "random": "Park-Miller 48271",
            "coverage": "4x4 ordered binary alpha",
            "png_optimize": False,
            "png_compress_level": 9,
        },
        "files": expected_records(),
    }
    INVENTORY_PATH.write_text(
        json.dumps(inventory, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def check() -> None:
    try:
        inventory = json.loads(INVENTORY_PATH.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise RuntimeError("public sky inventory is missing or invalid") from error
    if inventory.get("schema") != 1:
        raise RuntimeError("public sky inventory schema is invalid")
    if inventory.get("files") != expected_records():
        raise RuntimeError("public sky inventory does not match packaged files")
    for record in inventory["files"]:
        if png_size(ROOT / str(record["path"])) != (SIZE, SIZE):
            raise RuntimeError(f"sky texture dimensions changed: {record['path']}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("generate", "check"), nargs="?", default="check")
    args = parser.parse_args()
    if args.action == "generate":
        generate()
    check()
    print("cloud textures verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
