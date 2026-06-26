from pathlib import Path


ROOT = Path(__file__).parent
SERVER = (ROOT / "audiobook" / "server.py").read_text(encoding="utf-8")
INDEX = (ROOT / "audiobook" / "static" / "index.html").read_text(encoding="utf-8")


def test_server_local_saved_expires_in_one_hour():
    assert "expires_at = now_ts + (60 * 60)" in SERVER
    assert "expires_at = now_ts + (24 * 60 * 60)" not in SERVER


def test_client_tracks_offline_save_progress():
    assert "offlineSavingId: null" in INDEX
    assert "offlineSavingDone: 0" in INDEX
    assert "offlineSavingTotal: 0" in INDEX
    assert "Saving ${offlineSavingDone}/${offlineSavingTotal}" in INDEX


def test_client_verifies_cache_before_marking_local_saved():
    assert "async isBookCached(cache, job)" in INDEX
    assert "j.is_offline = await this.isBookCached(cache, j)" in INDEX
    assert "Cache verification failed" in INDEX
    verification_pos = INDEX.index("Cache verification failed")
    mark_saved_pos = INDEX.index("/local-saved")
    assert verification_pos < mark_saved_pos


def test_cached_expired_books_can_open_player():
    assert "job.device_state === 'Server Copy Expired' && !job.is_offline" in INDEX


if __name__ == "__main__":
    tests = [
        test_server_local_saved_expires_in_one_hour,
        test_client_tracks_offline_save_progress,
        test_client_verifies_cache_before_marking_local_saved,
        test_cached_expired_books_can_open_player,
    ]
    for test in tests:
        test()
    print("offline retention tests passed")
