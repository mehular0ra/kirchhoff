"""Pure formulas (spec §8.2), each unit-tested against a hand calculation. SI units unless the name says otherwise."""
import math

SQRT3 = math.sqrt(3.0)


def design_current_a(p_kw: float, u_v: float, pf: float) -> float:
    """I = P / (√3 · U · cosφ)."""
    return p_kw * 1000.0 / (SQRT3 * u_v * pf)


def sin_phi(pf: float) -> float:
    return math.sqrt(1.0 - pf * pf)


def z_eff_mohm_m(r_mohm_m: float, x_mohm_m: float, pf: float, n_parallel: int = 1) -> float:
    """R·cosφ + X·sinφ per metre of run, divided across parallel conductors."""
    return (r_mohm_m * pf + x_mohm_m * sin_phi(pf)) / n_parallel


def row_factor(n_taps: int) -> float:
    """Row busway with n equal, equally spaced tap-offs: (n + 1) / (2n)."""
    return (n_taps + 1) / (2.0 * n_taps)


def dv_pct(i_a: float, sections: list[tuple[float, float, float]], u_v: float) -> float:
    """ΔU% = 100 · √3 · I · Σ(L · z · factor) / U; sections are (length_m, z_eff_mohm_m, factor)."""
    ohms = sum(length * z * 1e-3 * factor for length, z, factor in sections)
    return 100.0 * SQRT3 * i_a * ohms / u_v


def transformer_kva(it_kw: float, aux_ups_kw: float, aux_other_kw: float, eta_ups: float, pf: float) -> float:
    """S = ((IT + UPS-backed aux) / η_UPS + other aux) / cosφ."""
    return ((it_kw + aux_ups_kw) / eta_ups + aux_other_kw) / pf


def transformer_loss_kw(p0_kw: float, pk_kw: float, s_kva: float, sn_kva: float) -> float:
    return p0_kw + pk_kw * (s_kva / sn_kva) ** 2


def ups_loss_kw(p_kw: float, eta: float) -> float:
    """UPS losses P · (1/η − 1)."""
    return p_kw * (1.0 / eta - 1.0)


def distributed_loss_factor(n_taps: int) -> float:
    """I²R loss factor of a run feeding n equal taps at equal spacing: (n+1)(2n+1)/(6n²)."""
    return (n_taps + 1) * (2 * n_taps + 1) / (6.0 * n_taps * n_taps)


def run_loss_kw(i_a: float, r_mohm_m: float, length_m: float, factor: float = 1.0, n_parallel: int = 1) -> float:
    """Three-phase I²R loss of a busway or cable run."""
    return 3.0 * i_a * i_a * (r_mohm_m * 1e-3 / n_parallel) * length_m * factor / 1000.0


def vol_flow_lps(q_kw: float, rho: float, cp_kj_kgk: float, dt_k: float) -> float:
    """V̇ = Q / (ρ · cp · ΔT) in L/s (ṁ = Q / (cp · ΔT))."""
    return q_kw / (cp_kj_kgk * dt_k) / rho * 1000.0


def area_m2(d_mm: float) -> float:
    return math.pi * (d_mm / 1000.0) ** 2 / 4.0


def velocity_ms(flow_lps: float, d_mm: float) -> float:
    """v = 4 · V̇ / (π · D²)."""
    return (flow_lps / 1000.0) / area_m2(d_mm)


def reynolds(v_ms: float, d_mm: float, rho: float, mu: float) -> float:
    return rho * v_ms * (d_mm / 1000.0) / mu


def swamee_jain(re: float, d_mm: float, eps_mm: float) -> float:
    """Darcy friction factor (turbulent), Swamee–Jain."""
    return 0.25 / math.log10(eps_mm / (3.7 * d_mm) + 5.74 / re ** 0.9) ** 2


def darcy_dp_pa(flow_lps: float, d_mm: float, length_m: float, rho: float, mu: float, eps_mm: float) -> float:
    """Darcy–Weisbach Δp = f · (L/D) · ρv²/2 (no fittings allowance)."""
    if flow_lps <= 0.0 or length_m <= 0.0:
        return 0.0
    v = velocity_ms(flow_lps, d_mm)
    f = swamee_jain(reynolds(v, d_mm, rho, mu), d_mm, eps_mm)
    return f * (length_m / (d_mm / 1000.0)) * rho * v * v / 2.0
