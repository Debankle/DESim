import numpy as np

from .base import PDEBase


class Heat2D(PDEBase):
    def __init__(self, nx, ny, dx, dy, alpha, ic, bc):
        super().__init__(nx, ny, dx, dy, ic, bc)
        self.alpha = alpha

    def F(self, u) -> np.ndarray:
        dudt = np.zeros_like(u)
        dudt[0, 1:-1, 1:-1] = self.alpha * (
            (u[0, 2:, 1:-1] - 2 * u[0, 1:-1, 1:-1] + u[0, :-2, 1:-1]) / self.dx**2
            + (u[0, 1:-1, 2:] - 2 * u[0, 1:-1, 1:-1] + u[0, 1:-1, :-2]) / self.dy**2
        )
        return dudt
