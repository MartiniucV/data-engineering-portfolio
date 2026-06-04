#!/usr/bin/env python3
"""
E-commerce order consumer: reads orders from Kafka and prints live revenue stats.
"""

import json
import logging
import signal
import sys
import time
from collections import defaultdict
from typing import Any

from kafka import KafkaConsumer
from kafka.errors import KafkaError, NoBrokersAvailable

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger(__name__)

KAFKA_BOOTSTRAP_SERVERS = "localhost:9092"
TOPIC = "orders"
CONSUMER_GROUP = "order-stats-consumer"
STATS_PRINT_INTERVAL = 10  # seconds between summary prints


class OrderStats:
    def __init__(self) -> None:
        self.total_revenue: float = 0.0
        self.order_count: int = 0
        self.revenue_by_category: dict[str, float] = defaultdict(float)
        self.orders_by_category: dict[str, int] = defaultdict(int)
        self.revenue_by_payment: dict[str, float] = defaultdict(float)
        self.start_time: float = time.monotonic()

    def ingest(self, order: dict[str, Any]) -> None:
        total = order.get("total_price", 0.0)
        category = order.get("category", "Unknown")
        payment = order.get("payment_method", "unknown")
        self.total_revenue += total
        self.order_count += 1
        self.revenue_by_category[category] += total
        self.orders_by_category[category] += 1
        self.revenue_by_payment[payment] += total

    @property
    def elapsed_seconds(self) -> float:
        return time.monotonic() - self.start_time

    @property
    def orders_per_minute(self) -> float:
        elapsed = self.elapsed_seconds
        return (self.order_count / elapsed * 60) if elapsed > 0 else 0.0

    @property
    def average_order_value(self) -> float:
        return self.total_revenue / self.order_count if self.order_count > 0 else 0.0

    def print_summary(self) -> None:
        separator = "─" * 55
        print(f"\n{separator}")
        print(f"  LIVE ORDER STATS  (elapsed: {self.elapsed_seconds:.0f}s)")
        print(separator)
        print(f"  Total orders   : {self.order_count:>8,}")
        print(f"  Total revenue  : ${self.total_revenue:>12,.2f}")
        print(f"  Avg order value: ${self.average_order_value:>12,.2f}")
        print(f"  Orders/min     : {self.orders_per_minute:>8.1f}")
        print(f"\n  Revenue by category:")
        for cat, rev in sorted(self.revenue_by_category.items(), key=lambda x: -x[1]):
            count = self.orders_by_category[cat]
            print(f"    {cat:<20} ${rev:>10,.2f}  ({count} orders)")
        print(f"\n  Revenue by payment method:")
        for method, rev in sorted(self.revenue_by_payment.items(), key=lambda x: -x[1]):
            print(f"    {method:<20} ${rev:>10,.2f}")
        print(separator)


def create_consumer(retries: int = 5, backoff: float = 3.0) -> KafkaConsumer:
    for attempt in range(1, retries + 1):
        try:
            consumer = KafkaConsumer(
                TOPIC,
                bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
                group_id=CONSUMER_GROUP,
                auto_offset_reset="earliest",
                enable_auto_commit=True,
                auto_commit_interval_ms=1000,
                value_deserializer=lambda raw: json.loads(raw.decode("utf-8")),
                consumer_timeout_ms=1000,  # raises StopIteration after 1s idle; lets us check shutdown flag
                max_poll_records=50,
            )
            logger.info("Connected to Kafka at %s, group='%s'", KAFKA_BOOTSTRAP_SERVERS, CONSUMER_GROUP)
            return consumer
        except NoBrokersAvailable:
            logger.warning("Attempt %d/%d: broker not available, retrying in %.0fs…", attempt, retries, backoff)
            if attempt < retries:
                time.sleep(backoff)
    logger.error("Could not connect to Kafka after %d attempts. Is the broker running?", retries)
    sys.exit(1)


def main() -> None:
    consumer = create_consumer()
    stats = OrderStats()
    last_summary = time.monotonic()
    running = True

    def shutdown(sig: int, frame: Any) -> None:
        nonlocal running
        logger.info("Shutdown signal received…")
        running = False

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    logger.info("Consuming from topic '%s'. Summary printed every %ds. Press Ctrl+C to stop.", TOPIC, STATS_PRINT_INTERVAL)

    try:
        while running:
            try:
                for message in consumer:
                    if not running:
                        break
                    try:
                        order = message.value
                        stats.ingest(order)
                        logger.info(
                            "order_id=%s  product='%s'  $%.2f  [total orders: %d]",
                            str(order.get("order_id", "?"))[:8],
                            order.get("product_name", "?"),
                            order.get("total_price", 0.0),
                            stats.order_count,
                        )
                    except (KeyError, TypeError, ValueError) as exc:
                        logger.warning("Skipping malformed message: %s", exc)
                    finally:
                        now = time.monotonic()
                        if now - last_summary >= STATS_PRINT_INTERVAL:
                            stats.print_summary()
                            last_summary = now
            except StopIteration:
                # consumer_timeout_ms elapsed with no messages — normal idle path
                now = time.monotonic()
                if now - last_summary >= STATS_PRINT_INTERVAL:
                    if stats.order_count > 0:
                        stats.print_summary()
                    last_summary = now
            except KafkaError as exc:
                logger.error("Kafka error: %s", exc)
                time.sleep(2)
    finally:
        consumer.close()
        if stats.order_count > 0:
            logger.info("Final stats:")
            stats.print_summary()
        logger.info("Consumer shut down cleanly.")


if __name__ == "__main__":
    main()
