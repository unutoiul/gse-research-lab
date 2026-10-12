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


def test_worker_count_follows_available_memory():
    from gse_research.resources import default_workers
    assert default_workers(available_gb=4.1, cpus=24) == 3          # (4.1 - 1.5) / 0.8
    assert default_workers(available_gb=30.0, cpus=24) == 16        # capped
    assert default_workers(available_gb=30.0, cpus=8) == 6          # CPUs - 2 on a desktop
    assert default_workers(available_gb=30.0, cpus=4) == 4          # small machines keep every core
    assert default_workers(available_gb=1.0, cpus=24) == 1          # never zero


def test_worker_count_override_and_small_machines(monkeypatch):
    from gse_research.resources import default_workers
    monkeypatch.setenv("GSE_WORKERS", "2")
    assert default_workers(available_gb=1.0, cpus=24) == 2
    monkeypatch.delenv("GSE_WORKERS")
    assert default_workers(available_gb=7.0, cpus=2) == 2   # a 2-core CI runner keeps both cores
