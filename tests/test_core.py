from __future__ import annotations

from quintara.core import DEFAULT_WEIGHTS, AppPaths, content_hash, runtime_identity


def test_content_hash_is_stable_and_weights_are_frozen(tmp_path):
    assert content_hash({"b": 1, "a": 2}) == content_hash({"a": 2, "b": 1})
    assert sum(DEFAULT_WEIGHTS) == 1.0
    paths = AppPaths.discover(tmp_path)
    paths.ensure()
    assert paths.registry.parent == tmp_path


def test_runtime_identity_contains_cpu_and_python():
    identity = runtime_identity()
    assert identity.cpu_count >= 1
    assert identity.python.count(".") >= 1
