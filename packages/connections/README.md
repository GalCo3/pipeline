# Connections

`connections` is a shared internal Python library that provides **standardized, reusable, and type-safe interfaces** for interacting with external services. 

It centralizes connections logic, enforces consistent configuration patterns via Pydantic, reduces boilerplate, and makes integrations easier to test, maintain, and evolve.

---

## Supported Services & Client Packages

| Service | Client/Library | Configuration Model | Factory / Handler |
| :--- | :--- | :--- | :--- |
| **Kafka Admin** | `confluent-kafka` | `BaseAdminConfig` | `BaseAdminHandler` / `create_kafka_admin_client` |
| **Kafka Consumer** | `confluent-kafka` | `BaseConsumerConfig` | `BaseConsumerHandler` / `create_kafka_consumer` |
| **Kafka Producer** | `confluent-kafka` | `BaseProducerConfig` | `BaseProducerHandler` / `create_kafka_producer` |
| **Kafka Schema Registry** | `confluent-kafka` | `BaseSchemaRegistryConfig` | `SchemaRegistryHandler` / `create_schema_registry_client` |
| **Elasticsearch** | `elasticsearch` | `BaseElasticConfig` | `ElasticsearchHandler` / `create_elasticsearch_client` |
| **MongoDB** | `pymongo` | `BaseMongoConfig` (`auth`: `X509Auth` / `BasicAuth`) | `BaseMongoHandler` / `create_mongo_clients` |
| **MongoDB (async)** | `pymongo` `AsyncMongoClient` | `BaseMongoConfig` (`auth`: `X509Auth` / `BasicAuth`) | `BaseAsyncMongoHandler` / `create_async_mongo_clients` |
| **PostgreSQL** | `psycopg2` | `BasePostgresConfig` | `create_simple_postgres_connection` / `create_postgres_connection_pool` |
| **S3 Compatible Storage** | `boto3` | `BaseS3Config` | `S3Handler` / `create_s3_client` |

---

## Design Pattern

The library is built around a consistent three-tier architecture:

1. **Config Models**: Pydantic models (under `hermes.connections.config_models`) validate configuration inputs (e.g., hosts, credentials, SSL paths, timeout settings) and enforce strict schema verification.
2. **Client Factories**: Lower-level factory functions (under `hermes.connections.factories`) instantiate the raw underlying clients (e.g., `MongoClient`, `AdminClient`, `boto3.client`) with the validated parameters.
3. **Handlers**: High-level classes (under `hermes.connections.handlers`) wrap client instances to manage connection lifetime, handle retries, and expose simplified APIs for common service operations.

---

## Installation

You can synchronize and install project dependencies locally using `uv`:

```bash
python -m uv sync
```

Or add it to another project:
```bash
uv add hermes-connections --index <internal-registry-url>
```

---

## Quick Start Examples

### 1. Kafka Admin Client

```python
from hermes.connections.config_models.kafka import BaseAdminConfig
from hermes.connections.config_models.ssl import SSL
from hermes.connections.handlers.admin import BaseAdminHandler

# Configure connection & credentials
config = BaseAdminConfig(
    bootstrap_servers="localhost:9092",
    ssl=SSL(ca_path="/path/to/ca.pem", cert_path="/path/to/cert.pem", key_path="/path/to/key.pem"),
)

# Initialize the handler
handler = BaseAdminHandler(config=config)

# Access the underlying confluent-kafka AdminClient
admin_client = handler.kafka_admin
```

### 2. MongoDB Client (with Basic Auth)

```python
from hermes.connections.config_models.mongo import BaseMongoConfig, BasicAuth
from hermes.connections.handlers.mongo import BaseMongoHandler
from pydantic import SecretStr

config = BaseMongoConfig(
    local_host="localhost",
    port=27017,
    database="my_database",
    auth=BasicAuth(
        username="admin",
        password=SecretStr("supersecret"),
    ),
)

# Initialize the handler
handler = BaseMongoHandler(config=config)

# Find a document using built-in error handling & retries
local_res, remote_res = handler.find_one(
    database="my_database", collection="users", query={"email": "user@example.com"}
)

if local_res.is_success:
    print("User document:", local_res.response)
```

### 3. PostgreSQL Connection

```python
from hermes.connections.config_models.postgres import BasePostgresConfig
from hermes.connections.factories.postgres import create_simple_postgres_connection

config = BasePostgresConfig(
    host="localhost",
    database="production_db",
    user="postgres_user",
    auth="my_db_password",
    port=5432,
)

# Create a connection
conn = create_simple_postgres_connection(config=config)
with conn.cursor() as cur:
    cur.execute("SELECT version();")
    print(cur.fetchone())
conn.close()
```

---

## Development & Testing

### Code Quality & Formatting
We use `ruff` to enforce lint rules and style conventions:

```bash
# Run linter
python -m uv run ruff check src/

# Run formatter
python -m uv run ruff format src/
```

### Building the Package
To build distribution bundles (source and wheel):

```bash
python -m uv build
```
Build distributions will reside under the `dist/` directory.
