import importlib.util
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "generate_cloud_textures", ROOT / "tools" / "generate_cloud_textures.py"
)
CLOUDS = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(CLOUDS)


class CloudTextureTests(unittest.TestCase):
    def test_public_inventory_matches_packaged_files(self):
        CLOUDS.check()

    def test_generation_is_deterministic_and_binary_alpha(self):
        first = CLOUDS.pixels(11, 0.60)
        second = CLOUDS.pixels(11, 0.60)
        self.assertEqual(first, second)
        self.assertEqual({pixel[3] for pixel in first}, {0, 255})
        self.assertGreater(sum(pixel[3] == 255 for pixel in first), 0)
        self.assertGreater(sum(pixel[3] == 0 for pixel in first), 0)

    def test_layers_are_distinct_and_bounded(self):
        outputs = {
            tuple(CLOUDS.pixels(int(layer["seed"]), float(layer["cut"])))
            for layer in CLOUDS.LAYERS
        }
        self.assertEqual(len(outputs), 3)
        self.assertTrue(all(len(output) == CLOUDS.SIZE**2 for output in outputs))

    def test_periodic_masks_have_no_abnormal_wrap_edge(self):
        def distance(left, right):
            return sum(abs(a - b) for a, b in zip(left, right)) / (255 * 4)

        for layer in CLOUDS.LAYERS:
            output = CLOUDS.pixels(int(layer["seed"]), float(layer["cut"]))
            size = CLOUDS.SIZE
            horizontal_wrap = sum(
                distance(output[y * size + size - 1], output[y * size])
                for y in range(size)
            ) / size
            vertical_wrap = sum(
                distance(output[(size - 1) * size + x], output[x])
                for x in range(size)
            ) / size
            # The authored style holds each noise sample for a 4-pixel block.
            # Compare the wrap to equivalent block transitions, not to the
            # many deliberately identical neighbors inside each block.
            horizontal_inside = sum(
                distance(output[y * size + x - 1], output[y * size + x])
                for y in range(size)
                for x in range(4, size, 4)
            ) / (size * ((size - 1) // 4))
            vertical_inside = sum(
                distance(output[(y - 1) * size + x], output[y * size + x])
                for y in range(4, size, 4)
                for x in range(size)
            ) / (size * ((size - 1) // 4))
            self.assertLessEqual(horizontal_wrap, horizontal_inside * 1.25)
            self.assertLessEqual(vertical_wrap, vertical_inside * 1.25)


if __name__ == "__main__":
    unittest.main()
