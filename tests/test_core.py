import math
import unittest

from dem_optimizer_art.dem import Surface, normalize, resample
from dem_optimizer_art.optimizers import EQUATIONS, OPTIMIZER_COLORS, equation_lines, find_high_disagreement_starts, run
from dem_optimizer_art.render import _clean_trajectory, _direction_chevron, _trajectory_d
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

    def test_all_optimizers_ascend_a_bowl(self):
        surface = Surface(normalize(bowl()))
        for name in OPTIMIZER_COLORS:
            with self.subTest(optimizer=name):
                path = run(surface, name, (-1.0, -1.0), 8, "ascent")
                self.assertGreater(surface.value(*path[-1]), surface.value(*path[0]))
        self.assertIn("+", equation_lines("ascent")["SGD"][0])

    def test_step_length_scales_an_update(self):
        surface = Surface(normalize(bowl()))
        start = (-1.0, -1.0)
        short = run(surface, "SGD", start, 1, step_length=0.5)[-1]
        long = run(surface, "SGD", start, 1, step_length=1.5)[-1]
        self.assertGreater(math.dist(start, long), math.dist(start, short))

    def test_wall_art_trajectory_treatment(self):
        points = [(0, 0), (0.2, 0.2), (5, 4), (9, 3), (12, 7)]
        cleaned = _clean_trajectory(points)
        self.assertEqual(cleaned, [(0, 0), (5, 4), (9, 3), (12, 7)])
        self.assertIn(" C ", _trajectory_d(cleaned))
        self.assertTrue(_direction_chevron(cleaned).startswith("M "))

    def test_high_disagreement_starts_are_spatially_distinct(self):
        surface = Surface(normalize(bowl()))
        descent = find_high_disagreement_starts(surface, list(OPTIMIZER_COLORS), 18, count=3)
        ascent = find_high_disagreement_starts(surface, list(OPTIMIZER_COLORS), 18, "ascent", count=3)
        self.assertEqual(len(descent), 3)
        self.assertEqual(len(ascent), 3)
        self.assertTrue(all(0.14 <= value <= 0.86 for point in descent + ascent for value in point))
        self.assertTrue(all(math.dist(a, b) >= 0.22 for points in (descent, ascent) for i, a in enumerate(points) for b in points[i + 1:]))
        to_surface = lambda point: (-3 + 6 * point[0], -3 + 6 * point[1])
        self.assertGreater(
            sum(surface.value(*to_surface(point)) for point in descent) / len(descent),
            sum(surface.value(*to_surface(point)) for point in ascent) / len(ascent),
        )

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
