from kirchhoff.engine.benchmark import mutations, run_benchmark

ALL_RULES = {"R01", "R02", "R03", "R04", "R04b", "R05", "R06", "R07", "R08", "R09", "R10", "R11", "R12", "R13",
             "R14", "R15"}


def test_mutation_set_covers_every_rule():
    muts = mutations()
    assert 30 <= len(muts) <= 40
    assert {m.target for m in muts} == ALL_RULES
    assert len({m.id for m in muts}) == len(muts)


def test_benchmark_catch_rate_and_false_positives(scn, erp):
    report = run_benchmark(scn, erp)
    assert report["baseline_failing_rules"] == []
    assert report["mutations"] == len(mutations())
    assert report["catch_rate"] == 1.0, [d for d in report["details"] if not d["caught"]]
    assert report["false_positive_mutations"] == 0, [d for d in report["details"] if d["unexpected"]]
    assert set(report["rules_covered"]) == ALL_RULES
