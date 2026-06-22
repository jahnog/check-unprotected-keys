"""Unit tests for VisitedDirectoryTracker and DirectoryLimitExceededError."""

from __future__ import annotations

import pytest

from check_unprotected_keys.adapters.filesystem import (
    DirectoryLimitExceededError,
    VisitedDirectoryTracker,
)


def test_new_directory_returns_true_and_increments_count(tmp_path):
    tracker = VisitedDirectoryTracker(limit=10)
    assert tracker.try_visit(tmp_path) is True
    assert tracker.visited_count == 1


def test_same_directory_again_returns_false(tmp_path):
    tracker = VisitedDirectoryTracker(limit=10)
    tracker.try_visit(tmp_path)
    assert tracker.try_visit(tmp_path) is False
    assert tracker.visited_count == 1


def test_same_real_directory_via_symlink_returns_false(tmp_path):
    real_dir = tmp_path / "real"
    real_dir.mkdir()
    link = tmp_path / "link"
    link.symlink_to(real_dir)

    tracker = VisitedDirectoryTracker(limit=10)
    assert tracker.try_visit(real_dir) is True
    assert tracker.try_visit(link) is False
    assert tracker.visited_count == 1


def test_two_distinct_directories_both_return_true(tmp_path):
    dir_a = tmp_path / "a"
    dir_b = tmp_path / "b"
    dir_a.mkdir()
    dir_b.mkdir()

    tracker = VisitedDirectoryTracker(limit=10)
    assert tracker.try_visit(dir_a) is True
    assert tracker.try_visit(dir_b) is True
    assert tracker.visited_count == 2


def test_visited_count_reflects_unique_entries_only(tmp_path):
    dirs = [tmp_path / f"d{i}" for i in range(5)]
    for d in dirs:
        d.mkdir()

    tracker = VisitedDirectoryTracker(limit=10)
    for d in dirs:
        tracker.try_visit(d)
    for d in dirs:
        tracker.try_visit(d)  # visit again — should not increase count

    assert tracker.visited_count == 5


def test_hard_cap_raises_directory_limit_exceeded_error(tmp_path):
    dir_a = tmp_path / "a"
    dir_b = tmp_path / "b"
    dir_a.mkdir()
    dir_b.mkdir()

    tracker = VisitedDirectoryTracker(limit=1)
    tracker.try_visit(dir_a)

    with pytest.raises(DirectoryLimitExceededError) as exc_info:
        tracker.try_visit(dir_b)

    assert exc_info.value.limit == 1
    assert exc_info.value.path == dir_b


def test_hard_cap_error_attributes_are_correct(tmp_path):
    dir_a = tmp_path / "a"
    dir_b = tmp_path / "b"
    dir_a.mkdir()
    dir_b.mkdir()

    tracker = VisitedDirectoryTracker(limit=1)
    tracker.try_visit(dir_a)

    error = pytest.raises(DirectoryLimitExceededError, tracker.try_visit, dir_b)
    assert error.value.limit == 1
    assert "1" in str(error.value)


def test_nonexistent_path_raises_oserror(tmp_path):
    tracker = VisitedDirectoryTracker(limit=10)
    missing = tmp_path / "does_not_exist"

    with pytest.raises(OSError):
        tracker.try_visit(missing)


def test_visited_count_zero_initially():
    tracker = VisitedDirectoryTracker(limit=10)
    assert tracker.visited_count == 0
