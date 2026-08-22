import importlib.util
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "generate_panorama_variants", ROOT / "tools" / "generate_panorama_variants.py"
)
PANORAMAS = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(PANORAMAS)


class PanoramaVariantTests(unittest.TestCase):
    def test_public_inventory_matches_packaged_files(self):
        PANORAMAS.check()

    def test_locked_quality_dimensions_are_distinct(self):
        self.assertEqual(
            PANORAMAS.QUALITY_WIDTHS,
            {"HIGH": 4096, "BALANCED": 2048, "LOW": 1024},
        )
        records = PANORAMAS.expected_records()
        for quality, width in PANORAMAS.QUALITY_WIDTHS.items():
            selected = [item for item in records if item["quality"] == quality]
            self.assertEqual(len(selected), 4)
            self.assertTrue(all(item["width"] == width for item in selected))

    def test_derived_names_cannot_replace_sources(self):
        for source_name in PANORAMAS.SOURCE_FILES:
            self.assertNotEqual(
                PANORAMAS.derived_name(source_name, 2048), source_name
            )
            self.assertNotEqual(
                PANORAMAS.derived_name(source_name, 1024), source_name
            )


if __name__ == "__main__":
    unittest.main()
