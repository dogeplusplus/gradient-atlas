import math
import unittest

from dem_optimizer_art.dem import Surface, normalize, resample
from dem_optimizer_art.optimizers import EQUATIONS, OPTIMIZER_COLORS, run
from dem_optimizer_art.webapp import parse_multipart
from dem_optimizer_art.terrain_fetch import _zoom_for_bbox


def bowl(size=32):
    return [[((x / (size - 1) - 0.5) ** 2 + (y / (size - 1) - 0.5) ** 2)
             for x in range(size)] for y in range(size)]


class CoreTests(unittest.TestCase):
    def test_resample_and_normalize(self):
        grid = normalize(resample(bowl(), 20))
        self.assertEqual((len(grid), len(grid[0])), (20, 20))
        self.assertTrue(math.isclose(min(map(min, grid)), -1.8))
        self.assertTrue(math.isclose(max(map(max, grid)), 1.8))

    def test_all_optimizers_descend_a_bowl(self):
        surface = Surface(normalize(bowl()))
        for name in OPTIMIZER_COLORS:
            with self.subTest(optimizer=name):
                path = run(surface, name, (-1.5, -1.5), 12)
                self.assertLess(surface.value(*path[-1]), surface.value(*path[0]))
                self.assertIn(name, EQUATIONS)

    def test_local_ui_multipart_upload(self):
        boundary = "terrain-boundary"
        body = (
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"smoothing\"\r\n\r\n8\r\n"
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"terrain.csv\"\r\n"
            "Content-Type: text/csv\r\n\r\n1,2\n3,4\r\n"
            f"--{boundary}--\r\n"
        ).encode()
        fields, upload = parse_multipart(f"multipart/form-data; boundary={boundary}", body)
        self.assertEqual(fields["smoothing"], "8")
        self.assertEqual(upload, ("terrain.csv", b"1,2\n3,4"))

    def test_terrain_zoom_stays_bounded(self):
        self.assertGreaterEqual(_zoom_for_bbox(37.8, 37.7, -119.5, -119.7), 7)
        self.assertLessEqual(_zoom_for_bbox(37.8, 37.7, -119.5, -119.7), 12)


if __name__ == "__main__":
    unittest.main()
