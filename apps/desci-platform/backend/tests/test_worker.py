from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
import worker as worker_module  # noqa: E402


@pytest.fixture
def bio_worker(monkeypatch):
    stub_bus = MagicMock()
    stub_bus.is_connected = False
    monkeypatch.setattr(worker_module, "get_rabbitmq_bus", lambda: stub_bus)
    return worker_module.BioWorker()


def test_dispatch_job_runs_notice_collection_handler(bio_worker, monkeypatch):
    class StubScheduler:
        async def collect_all_notices(self):
            return [{"id": "n1"}, {"id": "n2"}]

    monkeypatch.setattr(worker_module, "get_scheduler", lambda: StubScheduler())

    result = bio_worker.dispatch_job("job.notices.collect", {})

    assert len(result) == 2
    assert result[0]["id"] == "n1"


def test_dispatch_job_rejects_unknown_routing_key(bio_worker):
    with pytest.raises(ValueError, match="Unsupported routing key"):
        bio_worker.dispatch_job("job.unknown", {})


def test_handle_job_acks_successful_dispatch(bio_worker, monkeypatch):
    monkeypatch.setattr(bio_worker, "dispatch_job", lambda routing_key, payload: {"ok": True})  # noqa: ARG005

    channel = MagicMock()
    method = SimpleNamespace(routing_key="job.notices.collect", delivery_tag="tag-1")

    bio_worker.handle_job(channel, method, None, json.dumps({}).encode("utf-8"))

    channel.basic_ack.assert_called_once_with(delivery_tag="tag-1")
    channel.basic_nack.assert_not_called()


def test_handle_job_nacks_unsupported_jobs_without_requeue(bio_worker):
    channel = MagicMock()
    method = SimpleNamespace(routing_key="job.unknown", delivery_tag="tag-2")

    bio_worker.handle_job(channel, method, None, json.dumps({}).encode("utf-8"))

    channel.basic_ack.assert_not_called()
    channel.basic_nack.assert_called_once_with(delivery_tag="tag-2", requeue=False)
