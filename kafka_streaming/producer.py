#!/usr/bin/env python3
"""
E-commerce order producer: generates fake orders and publishes them to Kafka.
"""

import json
import logging
import random
import signal
import sys
import time
from datetime import datetime, timezone
from typing import Any

from faker import Faker
from kafka import KafkaProducer
from kafka.errors import KafkaError, NoBrokersAvailable

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger(__name__)

KAFKA_BOOTSTRAP_SERVERS = "localhost:9092"
TOPIC = "orders"
PRODUCE_INTERVAL_SECONDS = 1.0

CATEGORIES = ["Electronics", "Clothing", "Books", "Home & Garden", "Sports", "Toys"]

PRODUCTS: dict[str, list[dict[str, Any]]] = {
    "Electronics": [
        {"name": "Wireless Headphones", "price": 89.99},
        {"name": "Bluetooth Speaker", "price": 49.99},
        {"name": "USB-C Hub", "price": 34.99},
        {"name": "Mechanical Keyboard", "price": 129.99},
        {"name": "Webcam HD", "price": 69.99},
    ],
    "Clothing": [
        {"name": "Running Shoes", "price": 74.99},
        {"name": "Denim Jacket", "price": 59.99},
        {"name": "Merino Wool Sweater", "price": 89.99},
        {"name": "Yoga Pants", "price": 44.99},
    ],
    "Books": [
        {"name": "Clean Code", "price": 34.99},
        {"name": "Designing Data-Intensive Apps", "price": 49.99},
        {"name": "The Pragmatic Programmer", "price": 39.99},
    ],
    "Home & Garden": [
        {"name": "Air Purifier", "price": 149.99},
        {"name": "Smart Thermostat", "price": 199.99},
        {"name": "LED Desk Lamp", "price": 29.99},
    ],
    "Sports": [
        {"name": "Foam Roller", "price": 24.99},
        {"name": "Resistance Bands Set", "price": 19.99},
        {"name": "Protein Shaker", "price": 14.99},
    ],
    "Toys": [
        {"name": "LEGO Classic Set", "price": 39.99},
        {"name": "Remote Control Car", "price": 54.99},
        {"name": "Building Blocks", "price": 29.99},
    ],
}


def build_order(fake: Faker) -> dict[str, Any]:
    category = random.choice(CATEGORIES)
    product = random.choice(PRODUCTS[category])
    quantity = random.randint(1, 5)
    return {
        "order_id": fake.uuid4(),
        "customer_id": fake.uuid4(),
        "customer_name": fake.name(),
        "customer_email": fake.email(),
        "product_name": product["name"],
        "category": category,
        "unit_price": product["price"],
        "quantity": quantity,
        "total_price": round(product["price"] * quantity, 2),
        "shipping_address": {
            "street": fake.street_address(),
            "city": fake.city(),
            "state": fake.state_abbr(),
            "zip": fake.zipcode(),
            "country": "US",
        },
        "payment_method": random.choice(["credit_card", "debit_card", "paypal", "apple_pay"]),
        "status": "pending",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


def on_send_success(record_metadata: Any) -> None:
    logger.debug(
        "Delivered to %s [partition %d] @ offset %d",
        record_metadata.topic,
        record_metadata.partition,
        record_metadata.offset,
    )


def on_send_error(exc: Exception) -> None:
    logger.error("Failed to deliver message: %s", exc)


def create_producer(retries: int = 5, backoff: float = 3.0) -> KafkaProducer:
    for attempt in range(1, retries + 1):
        try:
            producer = KafkaProducer(
                bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
                value_serializer=lambda v: json.dumps(v).encode("utf-8"),
                acks="all",
                retries=3,
                compression_type="gzip",
                linger_ms=5,
            )
            logger.info("Connected to Kafka at %s", KAFKA_BOOTSTRAP_SERVERS)
            return producer
        except NoBrokersAvailable:
            logger.warning("Attempt %d/%d: broker not available, retrying in %.0fs…", attempt, retries, backoff)
            if attempt < retries:
                time.sleep(backoff)
    logger.error("Could not connect to Kafka after %d attempts. Is the broker running?", retries)
    sys.exit(1)


def main() -> None:
    fake = Faker()
    producer = create_producer()

    sent = 0
    running = True

    def shutdown(sig: int, frame: Any) -> None:
        nonlocal running
        logger.info("Shutdown signal received, flushing…")
        running = False

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    logger.info("Publishing orders to topic '%s' every %.1fs. Press Ctrl+C to stop.", TOPIC, PRODUCE_INTERVAL_SECONDS)

    while running:
        try:
            order = build_order(fake)
            producer.send(TOPIC, value=order).add_callback(on_send_success).add_errback(on_send_error)
            sent += 1
            logger.info(
                "[%d sent] order_id=%s  product='%s'  total=$%.2f",
                sent,
                order["order_id"][:8],
                order["product_name"],
                order["total_price"],
            )
            time.sleep(PRODUCE_INTERVAL_SECONDS)
        except KafkaError as exc:
            logger.error("Kafka error: %s", exc)
            time.sleep(2)

    producer.flush()
    producer.close()
    logger.info("Producer shut down cleanly. Total messages sent: %d", sent)


if __name__ == "__main__":
    main()
