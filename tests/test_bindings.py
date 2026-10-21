import mlba_sim


def test_bindings_report_pinned_versions():
    assert mlba_sim.game_version() == "1.0.1o"
    assert mlba_sim.smods_version() == "26.1002.0"
