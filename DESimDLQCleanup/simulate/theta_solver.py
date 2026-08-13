import numpy as np
from scipy.sparse.linalg import LinearOperator, gmres

from simulate.equations import PDEBase


class ThetaMethod:
    def __init__(
        self,
        pde: PDEBase,
        theta: float,
        dt: float,
        tol: float = 1e-8,
        maxiters: int = 20,
        linesearching: bool = False,
    ):
        self.pde = pde
        self.theta = theta
        self.dt = dt
        self.tol = tol
        self.maxiters = maxiters
        self.linesearching = linesearching

    def _newton_jfnk_solve(
        self, G, v_flat, N, tol, maxiters, linesearching
    ) -> np.ndarray:
        sqrt_eps = np.sqrt(np.finfo(float).eps)

        for _ in range(maxiters):
            Gv = G(v_flat)
            normG = np.linalg.norm(Gv)
            if normG < tol:
                break

            v_norm = np.linalg.norm(v_flat, 2)

            def matvec(p):
                p = np.asarray(p)
                p_norm = np.linalg.norm(p)
                if p_norm == 0:
                    return np.zeros_like(p)
                eps = sqrt_eps * max(1.0, float(v_norm)) / p_norm
                return (G(v_flat + eps * p) - Gv) / eps

            J_linop = LinearOperator((N, N), matvec)

            gmres_tol = min(0.5, 0.1 * min(1, tol))
            restart = min(50, max(20, int(N**0.5)))
            maxiter = 4
            delta_v, info = gmres(
                J_linop, -Gv, rtol=gmres_tol, restart=restart, maxiter=maxiter
            )
            if info != 0:
                delta_v = -Gv * (1.0 / (1.0 + normG))

            if linesearching:
                lam = 1.0
                Gv_norm = normG
                while lam > tol:
                    v_trial = v_flat + lam * delta_v
                    G_trial = G(v_trial)
                    if np.linalg.norm(G_trial) < Gv_norm:
                        v_flat = v_trial
                        break
                    lam *= 0.5
                else:
                    v_flat += delta_v
            else:
                v_flat += delta_v

        return v_flat

    def step(self, u) -> np.ndarray:
        theta = self.theta
        F = self.pde.F
        if theta == 0:
            u_new = u + self.dt * F(u)
            self.pde.apply_bc(u_new)
            return u_new

        else:
            u_flat = u.flatten()
            f_u_flat = F(u).flatten()
            v_flat = u_flat + self.dt * f_u_flat

            def G(v_flat):
                v = v_flat.reshape(u.shape)
                return (
                    v.flatten()
                    - u_flat
                    - self.dt * ((1 - theta) * f_u_flat + theta * F(v).flatten())
                )

            N = len(u_flat)
            v_flat = self._newton_jfnk_solve(
                G, v_flat, N, self.tol, self.maxiters, self.linesearching
            )

            v_new = v_flat.reshape(u.shape)
            self.pde.apply_bc(v_new)
            return v_new
