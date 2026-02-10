# https://stackoverflow.com/questions/75560981/how-to-interpolate-position-using-velocity-and-position-samples
#
from typing import Callable

import numpy as np
from numpy.linalg import solve


class GaussianRBF:
    def __init__(self, eps: float = 1.0):
        self.eps = eps

    def kernel(self, r: np.ndarray) -> np.ndarray:
        return np.exp(-(self.eps**2) * r**2)

    def kernel_prime(self, r: np.ndarray) -> np.ndarray:
        return -2 * self.eps**2 * r * self.kernel(r)

    def kernel_prime_prime(self, r: np.ndarray) -> np.ndarray:
        return (4 * self.eps**4 * r**2 - 2 * self.eps**2) * self.kernel(r)


class MultiquadricRBF:
    def __init__(self, eps: float = 1.0):
        self.eps = eps

    def kernel(self, r: np.ndarray) -> np.ndarray:
        return np.sqrt(1 + (self.eps * r) ** 2)

    def kernel_prime(self, r: np.ndarray) -> np.ndarray:
        return (self.eps**2 * r) / self.kernel(r)

    def kernel_prime_prime(self, r: np.ndarray) -> np.ndarray:
        return self.eps**2 / self.kernel(r) ** 3


def hermite_rbf_interpolation(
    times: np.ndarray,
    positions: np.ndarray,
    velocities: np.ndarray,
    kernel_class=MultiquadricRBF(),
) -> Callable[[np.ndarray], np.ndarray]:
    """
    Hermite RBF interpolation: construct a smooth interpolator that matches
    both position and velocity at given times.

    Args:
        times (np.ndarray): Shape (n,) — time points.
        positions (np.ndarray): Shape (n, m) — positions at time points.
        velocities (np.ndarray): Shape (n, m) — velocities at time points.
        kernel_class: Class implementing kernel, kernel_prime, kernel_prime_prime.

    Returns:
        Callable: Function that takes a 1D array of times and returns interpolated positions.
    """
    n, m = positions.shape
    K = np.zeros((2 * n, 2 * n))

    # Construct Hermite RBF kernel matrix
    for i in range(n):
        for j in range(n):
            dt = times[i] - times[j]
            K[i, j] = kernel_class.kernel(dt)
            K[i, j + n] = kernel_class.kernel_prime(dt)
            K[i + n, j] = kernel_class.kernel_prime(dt)
            K[i + n, j + n] = kernel_class.kernel_prime_prime(dt)

    Y = np.vstack([positions, velocities])

    # Solve for coefficients in each dimension
    coeffs_list = []
    for dim in range(m):
        y = Y[:, dim]
        w = solve(K, y)
        coeffs_list.append(w)
    coeffs = np.array(coeffs_list)

    def interpolator(t: np.ndarray) -> np.ndarray:
        t = np.atleast_1d(t).reshape(-1, 1)
        result = []
        for dim in range(m):
            phi_mat = np.hstack(
                [
                    kernel_class.kernel(t - times.T),
                    kernel_class.kernel_prime(t - times.T),
                ]
            )
            result.append(phi_mat @ coeffs[dim])
        return np.stack(result, axis=1)

    return interpolator