import math
from typing import Dict, Literal, Optional, Tuple, Union

from pydantic import BaseModel, Field, model_validator

BYTES_PER_DOUBLE = 8
BUFFER_OVERHEAD = 3.0
FLOPS_PER_CELL = {"heat": 20, "diffusionavection": 60, "wave": 30}
STENCIL_NNZ = {"heat": 5, "diffusionadvection": 7, "wave": 7}

BCType = Literal["dirichlet", "neumann0"]


class ConstantIC(BaseModel):
    type: Literal["constant"]
    value: float


class FunctionIC(BaseModel):
    type: Literal["function"]
    expr: str


class GaussianIC(BaseModel):
    type: Literal["gaussian"]
    center: Tuple[float, float]
    sigma: float
    amplitude: float = 1.0


ICModel = Union[ConstantIC, FunctionIC, GaussianIC]


class BCModel(BaseModel):
    left: Optional[Tuple[BCType, float]] = None
    right: Optional[Tuple[BCType, float]] = None
    top: Optional[Tuple[BCType, float]] = None
    bottom: Optional[Tuple[BCType, float]] = None


class BaseParams(BaseModel):
    nx: int
    ny: int
    dx: float
    dy: float
    theta: float
    dt: float
    steps: int
    ic: ICModel = Field(..., discriminator="type")
    bc: Optional[BCModel] = None
    tol: Optional[float] = 1e-6
    maxiters: Optional[int] = 20
    linesearching: Optional[bool] = False

    def validate_params(self) -> tuple[bool, dict[str, str]]:
        stable = True
        errors = {}

        if self.nx <= 0:
            errors["nx"] = "nx must be greater than zero"
        if self.ny <= 0:
            errors["ny"] = "ny must be greater than zero"
        if self.dx <= 0:
            errors["dx"] = "dx must be greater than zero"
        if self.dy <= 0:
            errors["dy"] = "dy must be greater than zero"
        if self.dt <= 0:
            errors["dt"] = "dt must be greater than zero"
        if self.theta < 0:
            errors["theta"] = "theta must be non-negative"
        if self.steps <= 0:
            errors["steps"] = "steps must be positive"
        if self.maxiters and self.maxiters <= 0:
            errors["maxiters"] = "maxiters must be greater than 0"

        return stable, errors

    def _estimate_common(self) -> int:
        comps = 2 if isinstance(self, WaveParams) else 1
        N = comps * self.nx * self.ny

        if self.theta == 0:
            peak_bytes = 4 * N * 8
        else:
            gmres_k = min(min(50, max(20, int(N**0.5))), max(1, N))
            peak_vector_count = 6 + gmres_k + 2
            peak_bytes = peak_vector_count * N * 8

        overhead_bytes = int(0.05 * peak_bytes)
        total_bytes = int((peak_bytes + overhead_bytes) * 1.2)
        mb = math.ceil(total_bytes / (1024**2))
        return max(1, mb)


class HeatParams(BaseParams):
    alpha: float

    def validate_params(self):
        stable, errors = super().validate_params()

        if self.alpha <= 0:
            errors["alpha"] = "alpha must be greater than zero"

        if self.theta == 0:
            dt_max = (self.dx**2 * self.dy**2) / (
                2 * self.alpha * (self.dx**2 + self.dy**2)
            )
            if self.dt > dt_max:
                stable = False
                errors["stability"] = (
                    f"dt={self.dt} exceeds maximum stable {dt_max:.5e}"
                )

        return stable, errors

    def estimate_size(self) -> int:
        return self._estimate_common()


class DiffusionAdvectionParams(BaseParams):
    D: float
    v: Tuple[float, float]

    def validate_params(self):
        stable, errors = super().validate_params()

        if self.D < 0:
            errors["D"] = "D must be positive"

        if self.theta == 0:
            dt_max = (self.dx**2 * self.dy**2) / (
                2 * self.D * (self.dx**2 + self.dy**2)
            )
            if self.dt > dt_max:
                stable = False
                errors["stability_diffusion"] = (
                    f"dt={self.dt} exceeds max stable {dt_max:.5e} for diffusion"
                )

        cfl = abs(self.v[0]) * self.dt / self.dx + abs(self.v[1]) * self.dt / self.dy
        if cfl > 1:
            stable = False
            errors["stability_advection"] = f"CFL violated: {cfl:.5e} > 1"

        return stable, errors

    def estimate_size(self) -> int:
        return self._estimate_common()


class WaveParams(BaseParams):
    c: float
    ic_v: ICModel = Field(
        default_factory=lambda: ConstantIC(type="constant", value=0),
        discriminator="type",
    )

    def validate_params(self):
        stable, errors = super().validate_params()

        if self.c <= 0:
            errors["c"] = "c must be greater than zero"

        dt_max = 1 / (self.c * math.sqrt((1 / self.dx**2) + (1 / self.dy**2)))
        if self.dt > dt_max:
            stable = False
            errors["stability"] = f"dt={self.dt} exceeds maximum stable {dt_max:.5e}"

        return stable, errors

    def estimate_size(self) -> int:
        return self._estimate_common()


class SimulationParams(BaseModel):
    equation: Literal["heat", "diffusionadvection", "wave"]
    parameters: Union[HeatParams, DiffusionAdvectionParams, WaveParams]
    private: bool

    @model_validator(mode="before")
    @classmethod
    def convert_parameters(cls, values):
        equation = values.get("equation")
        params = values.get("parameters")

        if equation == "heat":
            values["parameters"] = HeatParams.model_validate(params)
        elif equation == "diffusionadvection":
            values["parameters"] = DiffusionAdvectionParams.model_validate(params)
        elif equation == "wave":
            values["parameters"] = WaveParams.model_validate(params)
        else:
            raise ValueError(f"Unknown equation type: {equation}")

        return values
