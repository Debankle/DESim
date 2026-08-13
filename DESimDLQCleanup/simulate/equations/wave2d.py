import numexpr as ne
import numpy as np

from .base import PDEBase


class Wave2D(PDEBase):
    def __init__(self, nx, ny, dx, dy, c, ic, bc, ic_v):
        super().__init__(nx, ny, dx, dy, ic, bc)
        self.c = c
        self.ic_v = ic_v

    def initial_condition(self):
        u0 = super().initial_condition()[0, :, :]
        v0 = self.initial_velocity()

        U0 = np.stack([u0, v0], axis=0)
        return U0

    def initial_velocity(self):
        spec = self.ic_v
        if spec["type"] == "constant":
            return np.full((self.nx, self.ny), spec["value"])
        else:
            X, Y = np.meshgrid(
                np.linspace(0, self.dx * (self.nx - 1), self.nx),
                np.linspace(0, self.dy * (self.ny - 1), self.ny),
                indexing="ij",
            )
            return ne.evaluate(spec["expr"], local_dict={"x": X, "y": Y, "pi": np.pi})

    def F(self, u):
        u, v = u[0], u[1]
        v_t = np.zeros_like(u)

        u_t = v
        v_t[1:-1, 1:-1] = (self.c**2) * (
            (u[2:, 1:-1] - 2 * u[1:-1, 1:-1] + u[:-2, 1:-1]) / self.dx**2
            + (u[1:-1, 2:] - 2 * u[1:-1, 1:-1] + u[1:-1, :-2]) / self.dy**2
        )

        return np.stack([u_t, v_t], axis=0)
