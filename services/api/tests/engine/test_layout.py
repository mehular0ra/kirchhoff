from kirchhoff.engine.layout import build_geometry, busway_ids, busway_line, place_racks, row_of_busway


def test_place_racks_default_candidate(scn):
    racks = place_racks(scn)
    assert len(racks) == 48
    r = racks[0]
    assert (r.id, r.row, r.x, r.y, r.kw, r.liquid_fraction, r.feeds) == ("R1-01", "R1", 6.0, 15.9, 132.0, 0.8,
                                                                         ("A-01", "B-01"))
    assert racks[7].id == "R1-08" and racks[7].y == 20.1
    assert racks[-1].feeds == ("A-06", "B-06")
    assert sum(r.kw for r in racks) == 6336.0


def test_busway_helpers(scn):
    assert busway_ids("R3") == ("A-03", "B-03")
    assert row_of_busway("B-03") == "R3"
    assert busway_line(scn, "A-03") == ((27.7, 15.6), (27.7, 20.4))
    assert busway_line(scn, "B-03") == ((28.3, 15.6), (28.3, 20.4))


def test_build_geometry(scn):
    g = build_geometry(scn)
    assert g.hall == (60.0, 36.0) and len(g.columns) == 24
    assert g.keepouts == [(10.0, 10.0, 18.0, 26.0)]
    assert g.rooms["A"] == (60.0, 0.0, 72.0, 10.0) and g.rooms["bay-Z2"] == (28.6, 28.0, 33.4, 33.0)
    assert g.tiers["busway"] == 3.2
