# Kafka Streaming — Real-Time E-Commerce Orders

A real-time data streaming pipeline that simulates an e-commerce platform. A producer generates synthetic orders and publishes them to a Kafka topic; a consumer reads those orders and surfaces live revenue analytics.

## Architecture

```
┌─────────────────────┐        ┌───────────────────────┐        ┌──────────────────────┐
│     producer.py     │        │   Kafka (KRaft mode)  │        │     consumer.py      │
│                     │        │                       │        │                      │
│  Faker → Order dict │──────▶ │   topic: "orders"     │──────▶ │  Revenue tracking    │
│  JSON serialisation │        │   localhost:9092       │        │  Category breakdown  │
│  gzip compression   │        │   single broker        │        │  Live stats print    │
└─────────────────────┘        └───────────────────────┘        └──────────────────────┘
```

### Message Schema

```json
{
  "order_id":        "uuid4",
  "customer_id":     "uuid4",
  "customer_name":   "string",
  "customer_email":  "string",
  "product_name":    "string",
  "category":        "Electronics | Clothing | Books | Home & Garden | Sports | Toys",
  "unit_price":      "float",
  "quantity":        "int  (1–5)",
  "total_price":     "float",
  "shipping_address": {
    "street": "string", "city": "string", "state": "string",
    "zip": "string", "country": "US"
  },
  "payment_method":  "credit_card | debit_card | paypal | apple_pay",
  "status":          "pending",
  "created_at":      "ISO-8601 UTC timestamp"
}
```

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Message broker | Apache Kafka 7.6 (KRaft, no Zookeeper) |
| Producer | kafka-python 2.0, Faker 25 |
| Consumer | kafka-python 2.0 |
| Infrastructure | Docker Compose |
| Language | Python 3.11+ |

## Prerequisites

- Docker & Docker Compose
- Python 3.11+

## Quick Start

### 1. Start Kafka

```bash
docker compose up -d
```

Wait ~10 seconds for the broker to be ready:

```bash
docker compose ps   # STATUS should show "healthy"
```

### 2. Install Python dependencies

```bash
pip install -r requirements.txt
```

### 3. Run the producer (terminal 1)

```bash
python producer.py
```

Outputs one log line per order sent, e.g.:

```
2024-01-15T12:00:01 [INFO] [1 sent] order_id=a3f2b1c4  product='Wireless Headphones'  total=$179.98
```

### 4. Run the consumer (terminal 2)

```bash
python consumer.py
```

Every 10 seconds a live summary is printed:

```
───────────────────────────────────────────────────────
  LIVE ORDER STATS  (elapsed: 60s)
───────────────────────────────────────────────────────
  Total orders   :       60
  Total revenue  :    $4,231.40
  Avg order value:       $70.52
  Orders/min     :      60.0

  Revenue by category:
    Electronics          $1,312.80  (18 orders)
    Clothing               $854.90  (12 orders)
    ...
```

### 5. Tear down

```bash
docker compose down -v   # -v removes the kafka-data volume
```

## Configuration

| Variable | Location | Default | Description |
|----------|----------|---------|-------------|
| `KAFKA_BOOTSTRAP_SERVERS` | producer.py / consumer.py | `localhost:9092` | Broker address |
| `PRODUCE_INTERVAL_SECONDS` | producer.py | `1.0` | Seconds between messages |
| `STATS_PRINT_INTERVAL` | consumer.py | `10` | Seconds between summary prints |
| `CONSUMER_GROUP` | consumer.py | `order-stats-consumer` | Kafka consumer group ID |

## Project Structure

```
kafka_streaming/
├── docker-compose.yml   # Single-broker Kafka in KRaft mode
├── producer.py          # Fake order generator + Kafka publisher
├── consumer.py          # Order consumer + live analytics
├── requirements.txt     # Python dependencies
└── README.md
```

## Key Design Decisions

- **KRaft mode** — no Zookeeper dependency; simpler single-node setup.
- **`acks="all"`** on the producer — guarantees the leader has written the message before returning.
- **`consumer_timeout_ms=1000`** — allows the consumer loop to check the shutdown flag periodically without blocking forever on an idle topic.
- **gzip compression** — reduces network and disk usage with no code changes on the consumer side.
- **Graceful shutdown** — both processes trap SIGINT/SIGTERM, flush in-flight messages, and print final stats before exiting.
