"""Test that the deps listing order is preserved on sys.path."""

import os
import sys
import unittest


def _find_path_indices(suffix: str) -> list[int]:
    """Find sys.path indices whose entries end with the suffix"""
    normalized = suffix.replace("/", os.sep)
    return [i for i, p in enumerate(sys.path) if p.endswith(normalized)]


class DepOrderTest(unittest.TestCase):
    """Test that dependency import paths appear on sys.path in deps order."""

    def test_deps_order_preserved(self) -> None:
        """The order of deps in the BUILD target must match sys.path order.

        When a rule lists deps = [A, B], A's import paths must appear before
        B's on sys.path. Without deterministic ordering, packages from one dep
        can shadow identically-named modules in another (e.g. pytest's py.py
        shim shadowing the real py package).
        """
        first_indices = _find_path_indices("/first")
        second_indices = _find_path_indices("/second")

        self.assertTrue(
            first_indices,
            f"Expected first library on sys.path.\nsys.path: {sys.path}",
        )
        self.assertTrue(
            second_indices,
            f"Expected second library on sys.path.\nsys.path: {sys.path}",
        )

        self.assertLess(
            first_indices[0],
            second_indices[0],
            "first (listed first in deps) must appear before second on sys.path.\n"
            f"  first at index {first_indices[0]}: {sys.path[first_indices[0]]}\n"
            f"  second at index {second_indices[0]}: {sys.path[second_indices[0]]}",
        )

    def test_transitive_deps_grouped_with_parent(self) -> None:
        """Transitive deps of A must appear before B when deps = [A, B].

        The first dep depends on pytest. All of pytest's transitive import
        paths must appear before the second dep's import path. This prevents
        a later dep's site-packages from shadowing modules expected by an
        earlier dep's transitive tree.
        """
        pytest_indices = _find_path_indices("__pytest/site-packages")
        second_indices = _find_path_indices("/second")

        self.assertTrue(
            pytest_indices,
            f"Expected pytest site-packages on sys.path.\nsys.path: {sys.path}",
        )
        self.assertTrue(
            second_indices,
            f"Expected second library on sys.path.\nsys.path: {sys.path}",
        )

        self.assertLess(
            pytest_indices[0],
            second_indices[0],
            "pytest (transitive dep of first) must appear before second on sys.path.\n"
            f"  pytest at index {pytest_indices[0]}: {sys.path[pytest_indices[0]]}\n"
            f"  second at index {second_indices[0]}: {sys.path[second_indices[0]]}",
        )


if __name__ == "__main__":
    unittest.main()
