from __future__ import annotations

from quintara.core import AppPaths
from quintara.platform import FileLock


def test_stale_lock_is_recovered(app_root):
    paths = AppPaths.discover(app_root)
    paths.ensure()
    paths.lock.write_text("not-json", encoding="utf-8")
    with FileLock(paths.lock):
        assert paths.lock.exists()
    assert not paths.lock.exists()
