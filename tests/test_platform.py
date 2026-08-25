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


def test_windows_invalid_handle_lock_is_recovered(tmp_path, monkeypatch):
    lock_path = tmp_path / "gui-instance.lock"
    lock_path.write_text('{"owner":"old","pid":123,"created":"old"}', encoding="utf-8")

    def invalid_handle(_pid: int, _signal: int) -> None:
        raise SystemError("<built-in function kill> returned a result with an exception set")

    monkeypatch.setattr("quintara.platform.os.kill", invalid_handle)
    lock = FileLock(lock_path)
    lock.acquire()
    assert lock_path.exists()
    lock.release()
    assert not lock_path.exists()
