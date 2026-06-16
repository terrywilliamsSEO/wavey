"""Numerical stability estimates for the lattice integrator."""

from __future__ import annotations

import math
from typing import Any

from .config import SimulationConfig


def estimate_stability(config: SimulationConfig) -> dict[str, Any]:
    """Return conservative dt guidance for the current spatial discretization."""

    max_stiffness = float(config.base_stiffness) * max(1.0, float(config.defect.stiffness_multiplier))
    max_coupling = float(config.coupling_strength) * max(1.0, float(config.defect.coupling_multiplier))
    dx = float(config.dx)
    dy = float(config.dy)
    omega_sq = max_stiffness + 4.0 * max_coupling / (dx * dx) + 4.0 * max_coupling / (dy * dy)
    omega = math.sqrt(max(omega_sq, 1e-12))
    recommended_dt_max = 0.5 / omega
    hard_stability_dt_max = 1.8 / omega
    warnings = []
    if config.dt > hard_stability_dt_max:
        warnings.append(
            "dt exceeds the hard stability estimate for the current dx/dy; rerun with a smaller dt before interpreting results."
        )
    elif config.dt > recommended_dt_max:
        warnings.append(
            "dt is above the conservative accuracy recommendation for the current dx/dy; consider a smaller dt."
        )
    return {
        "dx": dx,
        "dy": dy,
        "omega_max_estimate": omega,
        "recommended_dt_max": recommended_dt_max,
        "hard_stability_dt_max": hard_stability_dt_max,
        "dt_to_recommended_ratio": float(config.dt / recommended_dt_max) if recommended_dt_max > 0.0 else 0.0,
        "dt_to_hard_limit_ratio": float(config.dt / hard_stability_dt_max) if hard_stability_dt_max > 0.0 else 0.0,
        "warnings": warnings,
    }
