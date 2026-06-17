import math
import unittest

from dem_optimizer_art.dem import Surface, normalize, resample
from dem_optimizer_art.optimizers import EQUATIONS, OPTIMIZER_COLORS, run


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


if __name__ == "__main__":
    unittest.main()
