"""
BioLinker - Background Worker
Consumes jobs from RabbitMQ and executes long-running tasks.
"""

import json
import os
import signal
import sys
import time
from services.logging_config import get_logger, setup_logging
from services.rabbitmq_bus import get_rabbitmq_bus

# Initialize logging
_is_production = os.getenv("ENV", "development") == "production"
setup_logging(json_output=_is_production, log_level=os.getenv("LOG_LEVEL", "INFO"))
log = get_logger("biolinker.worker")

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
            self.bus._channel.queue_bind(
                exchange="biolinker_events",
                queue=self.queue_name,
                routing_key="job.#"
            )
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
            
            # TODO: Route to specific service based on routing_key
            # Example: if routing_key == "job.crawl.vc": run_vc_crawl(data)
            
            # Simulate work
            time.sleep(1)
            
            ch.basic_ack(delivery_tag=method.delivery_tag)
            log.info("job_completed", key=routing_key)
        except Exception as exc:
            log.error("job_processing_error", error=str(exc))
            # Negative ack with requeue if transient
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)

    def start(self):
        """Start the consumption loop."""
        log.info("worker_starting", queue=self.queue_name)
        
        if not self.setup_queue():
            log.error("worker_startup_failed")
            return

        self.bus._channel.basic_qos(prefetch_count=1)
        self.bus._channel.basic_consume(
            queue=self.queue_name, 
            on_message_callback=self.handle_job
        )

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
