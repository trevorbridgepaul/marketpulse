# 001. Use a Layered Monolith Instead of Microservices

## Status

Accepted

## Context

MarketPulse ingests market data, persists it, and serves it through a
REST API and (later) a WebSocket stream, to a React frontend. At the
current stage, there is one backend application, one database, and
one data provider (Alpaca). No component has a scaling, deployment,
or ownership requirement that is independent of the others. The goal
is to produce a well-tested, maintainable system, not to build
infrastructure for a scale or team size that does not yet exist.

## Decision

Build a single FastAPI application, internally separated into
distinct layers (routes, services, repositories, provider
integrations), rather than splitting ingestion, API serving, and
analytics into separate deployable services.

## Alternatives Considered

- **Microservices** (separate ingestion, API, and analytics services)
  — rejected: introduces network failure modes, service discovery,
  and cross-service deployment coordination with no current scaling
  need to justify the cost.
- **Event-driven architecture with Kafka or similar** — rejected: no
  multiple independent consumers or event-replay requirement exists
  yet; this would add a new piece of infrastructure to operate and
  test without a concrete use case driving it.
- **Serverless functions per endpoint** — rejected: fragments a small
  codebase, complicates local development and end-to-end testing, and
  provides no benefit at this data volume or request rate.

## Benefits

- Simple local development: one backend process, one database, no
  cross-service orchestration.
- No distributed-transaction or partial-failure-across-services
  complexity to design around.
- Internal layering still provides clean seams for unit testing —
  each layer can be tested with the layer below it mocked.
- Faster iteration: no coordination overhead across independently
  deployed services.

## Tradeoffs

- Ingestion and API serving cannot be scaled or deployed
  independently of each other.
- A single codebase and deploy unit — a defect in one layer can, in
  principle, affect the whole process (mitigated by layering and
  tests, not eliminated by them).
- Layering is an enforced convention, not a hard runtime boundary;
  nothing prevents business logic from leaking into routes without
  active code review.

## Conditions for Reconsideration

A layered monolith is sufficient while there is one data provider,
one database, and request/ingestion volume that a single process can
comfortably serve. Microservices or event-driven processing would
become justified if:

- Ingestion workload grows large or bursty enough to require scaling
  independently from the read-facing API.
- Multiple independent consumers of market data events emerge,
  creating a genuine case for an event bus rather than direct calls.
- Real-time streaming load characteristics diverge significantly from
  REST API load, such that co-locating them in one process becomes an
  operational bottleneck.
- Separate deployable services become necessary as an ownership or
  release boundary, e.g., if the project grows beyond a single
  developer.
