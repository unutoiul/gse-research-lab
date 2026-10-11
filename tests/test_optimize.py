"""O1 search space: reproducible, valid TradingView inputs only, defaults included."""

from gse_research import optimize, structure


def test_sampling_is_reproducible_unique_and_starts_with_the_defaults():
    a, b = optimize.sample_configs(50, 1), optimize.sample_configs(50, 1)
    assert a == b and len(a) == 51 and a[0] == optimize.canonical(optimize.DEFAULT)
    keys = [tuple(sorted(c.items())) for c in a]
    assert len(set(keys)) == len(keys)


def test_every_value_is_a_valid_indicator_input():
    for c in optimize.sample_configs(200, 2):
        assert 3 <= c["swing_len"] <= 50 and 2 <= c["zone_count"] <= 20
        assert 0.1 <= c["cluster_atr"] <= 3.0 and 0.02 <= c["eq_atr"] <= 1.0 and 0.5 <= c["space_mult"] <= 10.0
        structure.CoreParams(**{k: c[k] for k in optimize.CORE_KEYS})  # accepted by the port
        if not c["cluster_on"]:
            assert c["cluster_atr"] == optimize.DEFAULT["cluster_atr"]
