import pytest

from kirchhoff.engine import calc


def test_design_current_rack_and_row_busway():
    i = calc.design_current_a(132.0, 415.0, 0.95)
    assert i == pytest.approx(193.3, abs=0.05)
    assert 8 * i / 2 == pytest.approx(773, rel=0.01)
    assert 8 * i == pytest.approx(1546, rel=0.01)


def test_voltage_drop_hand_calcs():
    i = 8 * calc.design_current_a(132.0, 415.0, 0.95)
    z16 = calc.z_eff_mohm_m(0.0345, 0.0216, 0.95)
    z20 = calc.z_eff_mohm_m(0.0260, 0.0170, 0.95)
    zc = calc.z_eff_mohm_m(0.0958, 0.08, 0.95, n_parallel=8)
    row = (4.8, z16, calc.row_factor(8))
    assert calc.row_factor(8) == pytest.approx(9 / 16)
    assert calc.dv_pct(i, [(1.0, z16, 1.0)], 415.0) == pytest.approx(0.0255, abs=0.0002)  # %/m
    assert calc.dv_pct(i, [row], 415.0) == pytest.approx(0.07, abs=0.005)
    assert calc.dv_pct(i, [(82.0, z16, 1.0), row], 415.0) == pytest.approx(2.16, abs=0.02)
    assert calc.dv_pct(i, [(65.2, z16, 1.0), row], 415.0) == pytest.approx(1.73, abs=0.02)
    assert calc.dv_pct(i, [(82.0, z20, 1.0), row], 415.0) == pytest.approx(1.66, abs=0.02)
    assert calc.dv_pct(i, [(82.0, zc, 1.0), row], 415.0) == pytest.approx(0.84, abs=0.02)


def test_transformer_load_and_losses():
    # 2N board in failover: 16 racks x 132 kW, aux 100 kW of which 45 kW CDU pumps (UPS-backed)
    s = calc.transformer_kva(2112.0, 45.0, 55.0, 0.97, 0.95)
    assert s == pytest.approx(2399, abs=1)
    assert 100 * s / 2500 == pytest.approx(96, abs=0.5)
    assert 100 * s / 3150 == pytest.approx(76, abs=0.5)
    assert 100 * calc.transformer_kva(1056.0, 22.5, 27.5, 0.97, 0.95) / 3150 == pytest.approx(38, abs=0.5)
    assert calc.ups_loss_kw(2157.0, 0.97) == pytest.approx(66.71, abs=0.01)
    assert calc.transformer_loss_kw(4.2, 25.0, 1199.3, 3150.0) == pytest.approx(4.2 + 25 * (1199.3 / 3150) ** 2)
    assert calc.distributed_loss_factor(8) == pytest.approx(9 * 17 / 384)
    assert calc.run_loss_kw(1000.0, 0.0345, 100.0) == pytest.approx(10.35)


def test_cooling_hand_calcs():
    q = calc.vol_flow_lps(105.6, 1020.0, 3.95, 10.0)
    assert q * 60 == pytest.approx(157, abs=0.5)
    assert calc.velocity_ms(16 * q, 206.0) == pytest.approx(1.26, abs=0.01)
    assert calc.velocity_ms(8 * q, 154.0) == pytest.approx(1.13, abs=0.01)
    re = calc.reynolds(1.258, 206.0, 1020.0, 0.0015)
    assert re == pytest.approx(176_200, rel=0.01)
    f = calc.swamee_jain(re, 206.0, 0.15)
    assert f == pytest.approx(0.0202, abs=0.0005)
    dp = calc.darcy_dp_pa(16 * q, 206.0, 10.0, 1020.0, 0.0015, 0.15)
    assert dp == pytest.approx(f * (10 / 0.206) * 1020 * 1.258 ** 2 / 2, rel=0.01)
    assert calc.darcy_dp_pa(0.0, 206.0, 10.0, 1020.0, 0.0015, 0.15) == 0.0
