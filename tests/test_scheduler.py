"""Test scheduler module — cron parsing and should_fire."""
import sys, os, time, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from core import scheduler
from pathlib import Path


@pytest.fixture(autouse=True)
def isolated_scheduler(tmp_path, monkeypatch):
    """Redirect scheduler file to temp dir."""
    test_file = tmp_path / "scheduled.json"
    monkeypatch.setattr(scheduler, "FILE", test_file)
    yield tmp_path


def test_parse_cron_valid():
    result = scheduler.parse_cron("*/5 * * * *")
    assert result == ("*/5", "*", "*", "*", "*")


def test_parse_cron_invalid():
    assert scheduler.parse_cron("bad") is None
    assert scheduler.parse_cron("1 2 3") is None


def test_should_fire_wildcard():
    now = time.localtime()
    assert scheduler.should_fire("* * * * *", now) is True


def test_should_fire_specific_minute():
    now = time.localtime()
    minute = now.tm_min
    assert scheduler.should_fire(f"{minute} * * * *", now) is True
    assert scheduler.should_fire(f"{(minute + 1) % 60} * * * *", now) is False


def test_should_fire_step():
    now = time.localtime()
    if now.tm_min % 5 == 0:
        assert scheduler.should_fire("*/5 * * * *", now) is True


def test_should_fire_range():
    now = time.localtime()
    minute = now.tm_min
    assert scheduler.should_fire(f"{max(0, minute-1)}-{min(59, minute+1)} * * * *", now) is True


def test_should_fire_csv():
    now = time.localtime()
    minute = now.tm_min
    assert scheduler.should_fire(f"{minute},{(minute+1)%60} * * * *", now) is True


def test_create_and_list():
    job = scheduler.create("*/10 * * * *", "test prompt")
    assert job["id"] is not None
    assert job["cron"] == "*/10 * * * *"
    assert job["prompt"] == "test prompt"
    jobs = scheduler.list_jobs()
    assert len(jobs) >= 1
    assert any(j["prompt"] == "test prompt" for j in jobs)


def test_get_job():
    job = scheduler.create("* * * * *", "get me")
    found = scheduler.get(job["id"])
    assert found is not None
    assert found["prompt"] == "get me"


def test_delete_job():
    job = scheduler.create("* * * * *", "delete me")
    scheduler.delete(job["id"])
    assert scheduler.get(job["id"]) is None
