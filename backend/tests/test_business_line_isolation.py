"""YU-58 Stage1: business_line isolation on sources/tasks/alarms repos.

A repo with ``business_line=None`` sees everything (workers / migrations); a
repo called with a specific business_line sees only that tenant's rows.
"""

from __future__ import annotations

from app.api.models import Alarm, Source, Task
from app.api.repository import (
    InMemoryAlarmRepo,
    InMemorySourceRepo,
    InMemoryTaskRepo,
)


class TestSourceRepoBusinessLine:
    def test_list_with_business_line_filters_to_tenant(self):
        repo = InMemorySourceRepo()
        s1 = repo.create(Source(name="p1-cam", business_line="phase1"))
        repo.create(Source(name="p2-cam", business_line="phase2"))

        phase1 = repo.list(business_line="phase1")

        assert [s.id for s in phase1] == [s1.id]

    def test_list_without_filter_returns_all(self):
        repo = InMemorySourceRepo()
        repo.create(Source(name="p1", business_line="phase1"))
        repo.create(Source(name="p2", business_line="phase2"))

        assert len(repo.list()) == 2

    def test_get_with_other_business_line_returns_none(self):
        repo = InMemorySourceRepo()
        created = repo.create(Source(name="p1", business_line="phase1"))

        assert repo.get(created.id, business_line="phase2") is None
        assert repo.get(created.id, business_line="phase1") is not None

    def test_update_with_other_business_line_returns_none(self):
        repo = InMemorySourceRepo()
        created = repo.create(Source(name="p1", business_line="phase1"))
        created.name = "renamed"

        assert repo.update(created, business_line="phase2") is None

    def test_delete_with_other_business_line_returns_false(self):
        repo = InMemorySourceRepo()
        created = repo.create(Source(name="p1", business_line="phase1"))

        assert repo.delete(created.id, business_line="phase2") is False
        assert repo.get(created.id) is not None


class TestTaskRepoBusinessLine:
    def test_list_filters_by_business_line(self):
        repo = InMemoryTaskRepo()
        t1 = repo.create(Task(source_id="s1", business_line="phase1"))
        repo.create(Task(source_id="s2", business_line="phase2"))

        phase1 = repo.list(business_line="phase1")

        assert [t.id for t in phase1] == [t1.id]

    def test_get_with_other_business_line_returns_none(self):
        repo = InMemoryTaskRepo()
        created = repo.create(Task(source_id="s1", business_line="phase1"))

        assert repo.get(created.id, business_line="phase2") is None


class TestAlarmRepoBusinessLine:
    def test_list_filters_by_business_line(self):
        repo = InMemoryAlarmRepo()
        a1 = repo.create(Alarm(event_id="e1", ts_ms=1000, business_line="phase1"))
        repo.create(Alarm(event_id="e2", ts_ms=2000, business_line="phase2"))

        phase1 = repo.list(business_line="phase1")

        assert [a.id for a in phase1] == [a1.id]

    def test_get_with_other_business_line_returns_none(self):
        repo = InMemoryAlarmRepo()
        created = repo.create(Alarm(event_id="e1", business_line="phase1"))

        assert repo.get(created.id, business_line="phase2") is None

    def test_event_id_unique_across_business_lines(self):
        """event_id is globally unique (dedup key), NOT per-business_line —
        a phase2 alarm with the same event_id as a phase1 alarm is deduped."""
        repo = InMemoryAlarmRepo()
        assert repo.create(Alarm(event_id="dup", business_line="phase1")) is not None
        assert repo.create(Alarm(event_id="dup", business_line="phase2")) is None
