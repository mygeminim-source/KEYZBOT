"""Test rate limiting module."""
import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from core import rate_limit


def test_rate_limiter_allows_within_limit():
    limiter = rate_limit.RateLimiter(max_requests=5, window_seconds=60)
    for _ in range(5):
        assert limiter.is_allowed("user1") is True
    assert limiter.is_allowed("user1") is False


def test_rate_limiter_window_reset():
    limiter = rate_limit.RateLimiter(max_requests=2, window_seconds=0.1)
    assert limiter.is_allowed("user2") is True
    assert limiter.is_allowed("user2") is True
    assert limiter.is_allowed("user2") is False
    time.sleep(0.15)
    assert limiter.is_allowed("user2") is True


def test_rate_limiter_isolation():
    limiter = rate_limit.RateLimiter(max_requests=2, window_seconds=60)
    assert limiter.is_allowed("a") is True
    assert limiter.is_allowed("a") is True
    assert limiter.is_allowed("a") is False
    # Different key
    assert limiter.is_allowed("b") is True


def test_remaining():
    limiter = rate_limit.RateLimiter(max_requests=3, window_seconds=60)
    assert limiter.remaining("c") == 3
    limiter.is_allowed("c")
    assert limiter.remaining("c") == 2


def test_reset_single_key():
    limiter = rate_limit.RateLimiter(max_requests=1, window_seconds=60)
    limiter.is_allowed("d")
    assert limiter.is_allowed("d") is False
    limiter.reset("d")
    assert limiter.is_allowed("d") is True


def test_reset_all():
    limiter = rate_limit.RateLimiter(max_requests=1, window_seconds=60)
    limiter.is_allowed("e")
    limiter.is_allowed("f")
    limiter.reset()
    assert limiter.is_allowed("e") is True
    assert limiter.is_allowed("f") is True


def test_check_message_limit():
    # Uses global limiter — just verify it returns bool
    result = rate_limit.check_message_limit("test-session")
    assert isinstance(result, bool)


def test_check_upload_limit():
    result = rate_limit.check_upload_limit("test-session")
    assert isinstance(result, bool)


def test_get_remaining():
    remaining = rate_limit.get_remaining("test-session")
    assert isinstance(remaining, int)
    assert remaining >= 0
