"""Numpy test code

https://github.com/numpy/numpy/blob/v2.1.1/numpy/tests/test_matlib.py
"""

# mypy: ignore-errors

import unittest

import numpy as np
import numpy.matlib
from numpy.testing import assert_ as np_assert
from numpy.testing import assert_array_equal


class NumpyTests(unittest.TestCase):
    """Numpy tests

    These upstream tests have been converted from pytest to unit tests.
    """

    # pylint: disable=missing-function-docstring

    def test_empty(self) -> None:
        x = numpy.matlib.empty((2,))
        np_assert(isinstance(x, np.matrix))
        np_assert(x.shape, (1, 2))

    def test_ones(self) -> None:
        assert_array_equal(
            numpy.matlib.ones((2, 3)), np.matrix([[1.0, 1.0, 1.0], [1.0, 1.0, 1.0]])
        )

        assert_array_equal(numpy.matlib.ones(2), np.matrix([[1.0, 1.0]]))

    def test_zeros(self) -> None:
        assert_array_equal(
            numpy.matlib.zeros((2, 3)), np.matrix([[0.0, 0.0, 0.0], [0.0, 0.0, 0.0]])
        )

        assert_array_equal(numpy.matlib.zeros(2), np.matrix([[0.0, 0.0]]))

    def test_identity(self) -> None:
        x = numpy.matlib.identity(2, dtype=int)
        assert_array_equal(x, np.matrix([[1, 0], [0, 1]]))

    def test_eye(self) -> None:
        xc = numpy.matlib.eye(3, k=1, dtype=int)
        assert_array_equal(xc, np.matrix([[0, 1, 0], [0, 0, 1], [0, 0, 0]]))
        assert xc.flags.c_contiguous
        assert not xc.flags.f_contiguous

        xf = numpy.matlib.eye(3, 4, dtype=int, order="F")
        assert_array_equal(xf, np.matrix([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0]]))
        assert not xf.flags.c_contiguous
        assert xf.flags.f_contiguous

    def test_rand(self) -> None:
        x = numpy.matlib.rand(3)
        # check matrix type, array would have shape (3,)
        np_assert(x.ndim == 2)

    def test_randn(self) -> None:
        x = np.matlib.randn(3)
        # check matrix type, array would have shape (3,)
        np_assert(x.ndim == 2)

    def test_repmat(self) -> None:
        a1 = np.arange(4)
        x = numpy.matlib.repmat(a1, 2, 2)
        y = np.array([[0, 1, 2, 3, 0, 1, 2, 3], [0, 1, 2, 3, 0, 1, 2, 3]])
        assert_array_equal(x, y)


if __name__ == "__main__":
    unittest.main()
