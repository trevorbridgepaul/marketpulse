# 002. Historical Daily Stock Price Data Model

## Status

Accepted

## Context

Milestone 2 begins financial-data ingestion and persistence. The scope is
deliberately narrow: historical **daily** OHLCV bars for US equities,
sourced from a single provider (Alpaca), with no intraday timeframes, no
real-time streaming, and no authentication concerns. Before writing any
ORM models or migrations, the record identity model, adjusted-vs-unadjusted
handling, feed/provider identity, and idempotent-import behavior needed to
be settled, per the open questions already flagged in
[docs/architecture.md](../architecture.md).

## Decision

Two tables:

- `securities` — one row per tradeable security, keyed by a surrogate
  `BIGINT IDENTITY` primary key, with `symbol` enforced `UNIQUE` as the
  MVP identity.
- `daily_price_bars` — one row per `(security_id, session_date)`, also
  surrogate-keyed, with that pair enforced as a separate `UNIQUE`
  constraint (the natural/business key).

Key points of the model:

- **`NUMERIC(12, 4)`** for all price columns, never `FLOAT` — prices are
  decimal by nature and must not accumulate binary floating-point error.
- **`DATE`** for `session_date` — a daily bar represents a trading
  session, not a timestamped event; it has no time-of-day or time-zone
  component to preserve.
- **Raw, unadjusted prices only.** No `adjusted_close` or `is_adjusted`
  column exists. Alpaca's adjustment model has four modes (`raw`,
  `split`, `dividend`, `all`); a boolean cannot represent that
  unambiguously, so the raw-only policy is expressed by the absence of
  any adjusted-price column rather than by a flag.
- **Provider and feed are separate, enforced columns.** `data_provider`
  (vendor) and `feed` (the underlying market-data source within that
  vendor, e.g., Alpaca's IEX vs. SIP feed) are distinct `TEXT NOT NULL`
  columns, each pinned to exactly one allowed value today via `CHECK`
  constraints (`data_provider = 'alpaca'`, `feed = 'iex'`). Different
  feeds can legitimately produce different OHLCV values for the same
  security and date, so this is a real distinction, not a naming
  nicety.
- **`CHECK` constraints enforce OHLCV invariants** (`high` is the max of
  the four prices, `low` is the min, all prices positive, volume
  non-negative) at the database level, not only in application code.
- **Idempotent imports via conditional upsert:**
  `INSERT ... ON CONFLICT (security_id, session_date) DO UPDATE SET ...
  WHERE <columns> IS DISTINCT FROM EXCLUDED.<columns>`. This `WHERE`
  clause is what preserves or refreshes `updated_at`: a rerun of
  unchanged data is a true no-op (`updated_at` preserved), and any
  incoming row whose values actually differ from what's stored —
  whether that's a genuine provider correction or any other source of a
  changed value — causes `updated_at` to refresh. The mechanism detects
  a value difference; it cannot itself verify the difference was caused
  by a provider correction specifically.
- **No additional indexes** beyond the ones the two `UNIQUE` constraints
  create automatically. PostgreSQL B-tree indexes scan backward
  natively, so `ORDER BY session_date DESC` for a given security is
  already served by the `daily_price_bars` unique index — a separate
  descending index would be redundant write overhead with no measured
  benefit. Revisit only with real `EXPLAIN ANALYZE` evidence.

## Alternatives Considered

- **Adjusted-price columns on this table** — rejected: can't represent
  Alpaca's multi-mode adjustment model without ambiguity; deferred
  entirely until there's a concrete adjusted-analytics requirement.
- **Separate tables per timeframe (daily vs. minute, etc.)** — rejected:
  no timeframe beyond daily is in scope; would be speculative design for
  a requirement that doesn't exist yet.
- **Specialized time-series database (TimescaleDB, InfluxDB, etc.)** —
  rejected: current data volume (daily bars, bounded equity universe) is
  trivially small for plain PostgreSQL; would add operational
  infrastructure with no current scaling justification, same reasoning
  as [ADR 001](001-layered-monolith.md)'s rejection of Kafka/microservices.
- **Composite natural primary key `(security_id, session_date)`
  instead of a surrogate key** — rejected: a surrogate key keeps future
  foreign keys from other tables (e.g., a future corporate-actions
  table) single-column and cheap, while the natural key is still fully
  enforced via the separate `UNIQUE` constraint.
- **Raw provider JSON storage instead of normalized columns** —
  rejected: the OHLCV shape is precisely known and there is exactly one
  provider in scope; JSON storage defers validation to read-time and
  prevents `CHECK`-constraint enforcement.
- **A redundant descending index on `(security_id, session_date)`** —
  rejected after reconsideration: the unique constraint's index already
  supports efficient backward scans for the "most recent N days" query
  shape.

## Known Limitations and Future Implementation Requirements

These are accepted tradeoffs for the MVP, not open design problems to
solve today:

1. **The raw-only policy is not self-enforcing at the ingestion layer.**
   The absence of adjusted-price columns does **not** prevent adjusted
   data from being inserted — nothing in the schema inspects what values
   land in `open`/`high`/`low`/`close`, so an Alpaca client misconfigured
   to request `adjustment=split` or `adjustment=all` would have its
   adjusted values stored in those same raw-named columns without any
   database-level objection. Raw-only ingestion must be enforced through
   the Alpaca request configuration itself (explicitly passing
   `adjustment=raw`) and verified with a test that asserts the request
   was made that way — this is an implementation requirement for the
   ingestion/provider layer, not something the schema can guarantee.
2. **`now()` uses transaction-start time, not statement-execution time.**
   All writes inside one transaction share the same `now()` value. Tests
   that assert `updated_at` changed (a correction) or stayed the same (a
   no-op rerun) must account for this — e.g., by running the two upserts
   in separate transactions/connections — and must not rely on
   wall-clock `sleep()` between them to force a different timestamp.
3. **`symbol UNIQUE` is an MVP simplification of security identity, not
   a permanent guarantee.** The constraint only prevents two *rows* from
   existing with the same symbol at the same time — it does not
   guarantee that a given symbol always refers to the same real-world
   company. A ticker can be renamed or reused after a delisting, and if
   ingestion logic looks up (rather than creates) a security by symbol,
   a recycled ticker could resolve to the old, still-existing
   `security_id` and silently attach a new, unrelated company's
   historical bars to it — no constraint violation would occur, because
   no second row with that symbol was ever inserted. This is not a
   theoretical edge case to dismiss; it is a real gap in MVP identity
   handling. If this becomes a real problem, the migration path is
   additive: introduce a nullable `provider_asset_id TEXT UNIQUE` column
   backfilled from Alpaca's stable per-asset identifier, and shift
   identity to it while `symbol` becomes a display-only attribute.
4. **Single feed/provider is schema-enforced via `CHECK` constraints.**
   Supporting a second feed or provider requires a real migration:
   relax or drop the `CHECK` constraints, widen the natural key to
   `UNIQUE (security_id, session_date, feed)`, and update every
   `ON CONFLICT` target in ingestion code accordingly.
5. **No audit/history of corrections, no trading-calendar table, no
   intraday timeframes.** All deliberately out of scope for this
   milestone.

## Consequences

The schema is small, fully constrained at the database level, and
supports idempotent re-ingestion without ambiguity about what is stored
or where it came from. Extending it for a second feed, provider, or
adjustment mode is possible but requires a deliberate migration rather
than a silent application-level change — which is the intended
guardrail, not an oversight.
