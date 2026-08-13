from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Literal

import numexpr as ne
import numpy as np

BCType = Literal["dirichlet", "neumann0"]


@dataclass
class BC:
    left: tuple[BCType, float] | None = None
    right: tuple[BCType, float] | None = None
    top: tuple[BCType, float] | None = None
    bottom: tuple[BCType, float] | None = None


class PDEBase(ABC):
    def __init__(self, nx, ny, dx, dy, ic, bc):
        self.nx = nx
        self.ny = ny
        self.dx = dx
        self.dy = dy
        self.ic = ic
        self.bc = BC(**bc)

    def initial_condition(self):
        spec = self.ic
        X, Y = np.meshgrid(
            np.linspace(0, self.dx * (self.nx - 1), self.nx),
            np.linspace(0, self.dy * (self.ny - 1), self.ny),
            indexing="ij",
        )

        if spec["type"] == "constant":
            field = np.full((self.nx, self.ny), spec["value"])
        elif spec["type"] == "expression":
            field = ne.evaluate(spec["expr"], local_dict={"x": X, "y": Y, "pi": np.pi})
        elif spec["type"] == "gaussian":
            x0, y0 = spec["center"]
            sigma = spec["sigma"]
            A = spec.get("amplitude", 1.0)
            field = A * np.exp(-((X - x0) ** 2 + (Y - y0) ** 2) / (2 * sigma**2))
        else:
            raise ValueError(f"Unsupported initial condition type: {spec['type']}")

        return field[np.newaxis, :, :]

    def apply_bc(self, u):
        if self.bc.left:
            t, v = self.bc.left
            if t == "dirichlet":
                u[..., :, 0] = v
            else:
                u[..., :, 0] = u[..., :, 1] + v * self.dx
        if self.bc.right:
            t, v = self.bc.right
            if t == "dirichlet":
                u[..., :, -1] = v
            else:
                u[..., :, -1] = u[..., :, -2] - v * self.dx
        if self.bc.bottom:
            t, v = self.bc.bottom
            if t == "dirichlet":
                u[..., -1, :] = v
            else:
                u[..., -1, :] = u[..., -2, :] + v * self.dy
        if self.bc.top:
            t, v = self.bc.top
            if t == "dirichlet":
                u[..., 0, :] = v
            else:
                u[..., 0, :] = u[..., 1, :] - v * self.dy

    @abstractmethod
    def F(self, u) -> np.ndarray: ...
