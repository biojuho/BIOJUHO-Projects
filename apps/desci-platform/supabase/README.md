# Supabase / PostgreSQL Baseline

This directory captures the target relational data model for the DeSci platform.
The current runtime still uses Firebase Auth and Firestore-backed paths in a few
places, so this schema is a migration baseline rather than a required runtime
dependency today.

## Local Infra

Start the optional Postgres, Redis, and RabbitMQ stack:

```bash
docker compose --profile infra up postgres redis rabbitmq
```

The local Postgres URL from `.env.example` is:

```text
postgresql://desci:desci@localhost:5432/desci
```

## Supabase Direction

- Use Supabase/PostgreSQL as the canonical relational store for profiles,
  notices, research assets, matches, subscriptions, governance, and audit events.
- Keep direct browser writes behind the backend until Supabase Auth ownership is
  wired in. Frontend `VITE_SUPABASE_*` values are for future read-oriented use.
- Keep vector search in Chroma/Qdrant for now; store relational metadata and
  durable business records in Postgres.
