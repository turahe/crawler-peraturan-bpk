# Project documentation

This directory documents the maintained runtime: a Python crawler for Indonesian regulations published by BPK, backed by PostgreSQL and optional RustFS PDF storage.

## Start here

- [Setup and running](setup.md): environment, Docker Compose, and local commands.
- [Architecture](architecture.md): runtime components and their connections.
- [Crawler workflow](crawler.md): collection, retries, persistence, and PDF handling.
- [Data model](data-model.md): database entities and relationships.
- [Entity relationship diagram](erd.md): Mermaid ER diagram of the database schema.
- [Operations](operations.md): migrations, storage, troubleshooting, and important configuration.
- [Development](development.md): source layout and maintenance workflow.

The root [README](../README.md) remains the project overview and includes further implementation detail. The current requirements and workflow intent are also recorded in [PRD.md](../PRD.md).
