import numpy as np

from .base import PDEBase


class DiffusionAdvection(PDEBase):
    def __init__(self, nx, ny, dx, dy, D, v, ic, bc):
        super().__init__(nx, ny, dx, dy, ic, bc)
        self.D = D
        self.v = v

    def F(self, u):
        vx, vy = self.v
        dudt = np.zeros_like(u)

        f = u[0]

        laplacian = (f[2:, 1:-1] - 2 * f[1:-1, 1:-1] + f[:-2, 1:-1]) / self.dx**2 + (
            f[1:-1, 2:] - 2 * f[1:-1, 1:-1] + f[1:-1, :-2]
        ) / self.dy**2

        # Using upwinding because my poor eyes got flashbanged
        adv_x = vx * (f[1:-1, 1:-1] - f[:-2, 1:-1]) / self.dx
        adv_y = vy * (f[1:-1, 1:-1] - f[1:-1, :-2]) / self.dy

        dudt[0, 1:-1, 1:-1] = self.D * laplacian - adv_x - adv_y
        return dudt
