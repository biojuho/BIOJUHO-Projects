"""
BioLinker - Background Worker
Consumes jobs from RabbitMQ and executes long-running tasks.
"""

import asyncio
import json
import os
import signal
import sys

from services.logging_config import get_logger, setup_logging
from services.rabbitmq_bus import get_rabbitmq_bus

# Initialize logging
_is_production = os.getenv("ENV", "development") == "production"
setup_logging(json_output=_is_production, log_level=os.getenv("LOG_LEVEL", "INFO"))
log = get_logger("biolinker.worker")


def _load_service(module_path: str, getter_name: str):
    module = __import__(module_path, fromlist=[getter_name])
    return getattr(module, getter_name)()


def get_scheduler():
    return _load_service("services.scheduler", "get_scheduler")


def get_asset_manager():
    return _load_service("services.asset_manager", "get_asset_manager")


def get_rfp_matcher():
    return _load_service("services.matcher", "get_rfp_matcher")


def get_proposal_generator():
    return _load_service("services.proposal_generator", "get_proposal_generator")


def get_vector_store():
    return _load_service("services.vector_store", "get_vector_store")


class BioWorker:
    """RabbitMQ consumer for background processing."""

    def __init__(self):
        self.bus = get_rabbitmq_bus()
        self.queue_name = "biolinker_worker_tasks"
        self.should_stop = False

    def setup_queue(self):
        """Prepare the queue for consumption."""
        if not self.bus.is_connected:
            return False

        try:
            self.bus._channel.queue_declare(queue=self.queue_name, durable=True)
            self.bus._channel.queue_bind(exchange="biolinker_events", queue=self.queue_name, routing_key="job.#")
            return True
        except Exception as exc:
            log.error("worker_setup_error", error=str(exc))
            return False

    def handle_job(self, ch, method, properties, body):
        """Process an incoming message."""
        try:
            data = json.loads(body)
            routing_key = method.routing_key
            log.info("processing_job", key=routing_key, data=data)
            result = self.dispatch_job(routing_key, data)

            ch.basic_ack(delivery_tag=method.delivery_tag)
            log.info("job_completed", key=routing_key, result_type=type(result).__name__)
        except (json.JSONDecodeError, ValueError) as exc:
            log.error("job_rejected", error=str(exc), body_preview=str(body)[:200])
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
        except Exception as exc:
            log.error("job_processing_error", error=str(exc), key=getattr(method, "routing_key", "unknown"))
            # Negative ack with requeue if transient
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)

    def dispatch_job(self, routing_key: str, payload: dict):
        """Run the handler for the supplied routing key."""
        handlers = {
            "job.notices.collect": self._run_notice_collection,
            "job.papers.index": self._run_paper_index,
            "job.match.paper": self._run_paper_match,
            "job.proposal.generate": self._run_proposal_generation,
        }

        handler = handlers.get(routing_key)
        if handler is None:
            raise ValueError(f"Unsupported routing key: {routing_key}")
        return handler(payload)

    def _run_coroutine(self, coroutine):
        return asyncio.run(coroutine)

    def _run_notice_collection(self, payload: dict):  # noqa: ARG002
        scheduler = get_scheduler()
        if scheduler is None:
            raise RuntimeError("Notice scheduler is unavailable")
        return self._run_coroutine(scheduler.collect_all_notices())

    def _run_paper_index(self, payload: dict):
        paper_id = str(payload.get("paper_id") or "").strip()
        if not paper_id:
            raise ValueError("paper_id is required")

        asset_manager = get_asset_manager()
        return self._run_coroutine(
            asset_manager.reindex_paper(
                paper_id=paper_id,
                user=dict(payload.get("user", {}) or {}),
            )
        )

    def _run_paper_match(self, payload: dict):
        paper_id = str(payload.get("paper_id") or "").strip()
        if not paper_id:
            raise ValueError("paper_id is required")

        matcher = get_rfp_matcher()
        limit = int(payload.get("limit", 5) or 5)
        target_trl = payload.get("target_trl")
        enrich = bool(payload.get("enrich", False))

        try:
            return self._run_coroutine(
                matcher.match_paper(
                    paper_id=paper_id,
                    limit=limit,
                    target_trl=target_trl,
                    enrich=enrich,
                )
            )
        except TypeError:
            if target_trl is not None:
                try:
                    return self._run_coroutine(matcher.match_paper(paper_id=paper_id, limit=limit, target_trl=target_trl))
                except TypeError:
                    return self._run_coroutine(matcher.match_paper(paper_id=paper_id, limit=limit))
            return self._run_coroutine(matcher.match_paper(paper_id=paper_id, limit=limit))

    def _run_proposal_generation(self, payload: dict):
        paper_id = str(payload.get("paper_id") or "").strip()
        rfp_id = str(payload.get("rfp_id") or "").strip()
        if not paper_id or not rfp_id:
            raise ValueError("paper_id and rfp_id are required")

        vector_store = get_vector_store()
        paper = vector_store.get_notice(paper_id)
        if not paper:
            raise ValueError("Paper not found")

        rfp = vector_store.get_notice(rfp_id)
        if not rfp:
            raise ValueError("RFP not found")

        generator = get_proposal_generator()
        draft = self._run_coroutine(generator.generate_draft(rfp, paper))
        critique = self._run_coroutine(generator.review_draft(rfp, paper, draft))
        return {"draft": draft, "critique": critique}

    def start(self):
        """Start the consumption loop."""
        log.info("worker_starting", queue=self.queue_name)

        if not self.setup_queue():
            log.error("worker_startup_failed")
            return

        self.bus._channel.basic_qos(prefetch_count=1)
        self.bus._channel.basic_consume(queue=self.queue_name, on_message_callback=self.handle_job)

        log.info("worker_listening")
        try:
            self.bus._channel.start_consuming()
        except KeyboardInterrupt:
            self.stop()
        except Exception as exc:
            log.error("worker_runtime_error", error=str(exc))
            self.stop()

    def stop(self):
        """Gracefully stop the worker."""
        log.info("worker_stopping")
        if self.bus:
            self.bus.close()
        self.should_stop = True
        sys.exit(0)


def main():
    worker = BioWorker()

    # Handle termination signals
    signal.signal(signal.SIGINT, lambda s, f: worker.stop())
    signal.signal(signal.SIGTERM, lambda s, f: worker.stop())

    worker.start()


if __name__ == "__main__":
    main()
