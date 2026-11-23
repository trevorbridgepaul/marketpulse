![CI](https://github.com/trevorbridgepaul/marketpulse/actions/workflows/ci.yml/badge.svg)

# MarketPulse

MarketPulse is a full-stack financial market data analytics platform
under active development. It is designed to ingest and analyze
historical and real-time market data using Python, FastAPI,
PostgreSQL, React, and TypeScript.

## Project Goals

- Ingest historical and real-time financial market data
- Persist normalized market data reliably in PostgreSQL
- Expose that data through a well-tested REST API
- Present interactive analytics through a React/TypeScript frontend
- Demonstrate production-quality full-stack engineering practices

## Current Status

**Milestone 1 — Project Foundation** (in progress): backend and
frontend scaffolding, local PostgreSQL infrastructure, and CI are in
place. No market data ingestion, database schema, or analytics exist
yet.

### Implemented

- FastAPI backend with a `/health` endpoint and a pytest test suite
- React + TypeScript + Vite frontend with a static landing page built
  from a reusable `FeatureCard` component
- PostgreSQL 16 running locally via Docker Compose, with a named
  volume for data persistence (no schema yet)
- GitHub Actions CI running backend (Ruff, pytest) and frontend
  (oxlint, Vitest, production build) checks on every push and pull
  request targeting `main`

### Planned (not yet implemented)

- Alpaca API integration for historical and real-time market data
- Database schema, SQLAlchemy models, and Alembic migrations
- REST endpoints for querying historical prices
- Real-time price streaming via WebSocket
- Interactive charts and analytics in the frontend

See [docs/architecture.md](docs/architecture.md) for how these pieces
are intended to fit together.

## Technology Stack

- **Backend:** Python, FastAPI, Uvicorn
- **Frontend:** React, TypeScript, Vite
- **Database:** PostgreSQL
- **Market Data (planned):** Alpaca API
- **Local Infrastructure:** Docker Compose
- **Testing:** pytest (backend), Vitest + React Testing Library (frontend)
- **CI/CD:** GitHub Actions

## Prerequisites

- Python 3.11 or later
- Node.js 22 and npm
- Docker and Docker Compose
- Git

## Local Development

MarketPulse runs as three independent local processes during
development — PostgreSQL (in Docker), the FastAPI backend, and the
Vite dev server. They do not currently communicate with each other;
each is started and verified on its own.

Clone the repository:

```bash
git clone https://github.com/trevorbridgepaul/marketpulse.git
cd marketpulse
```

### Environment Configuration

Copy the example environment file and adjust values for local use:

```bash
cp .env.example .env
```

| Variable             | Purpose                                            |
|-----------------------|-----------------------------------------------------|
| `POSTGRES_USER`       | Database role used by the dev container             |
| `POSTGRES_PASSWORD`   | Local-only password (never commit `.env`)            |
| `POSTGRES_DB`         | Database name created on first container startup    |
| `POSTGRES_PORT`       | Host port Postgres is exposed on (`127.0.0.1` only)  |

### PostgreSQL

Start the database:

```bash
docker compose up -d
```

Check it's healthy:

```bash
docker compose ps
```

Stop it (data persists in the named volume):

```bash
docker compose down
```

Stop it **and delete all data**:

```bash
docker compose down -v
```

### Backend (FastAPI)

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
uvicorn app.main:app --reload
```

Visit `http://127.0.0.1:8000/health`.

Run tests:

```bash
pytest
```

Run linting:

```bash
ruff check .
```

### Frontend (React + Vite)

```bash
cd frontend
npm ci
npm run dev
```

Visit the URL Vite prints (typically `http://localhost:5173`).

Run tests:

```bash
npm run test
```

Run linting:

```bash
npm run lint
```

Build for production:

```bash
npm run build
```

`npm ci` is used here (rather than `npm install`) because
`package-lock.json` is committed — it installs exactly what's locked,
the same way CI does.

## Repository Structure

```
marketpulse/
├── backend/              # FastAPI application
│   ├── app/
│   │   └── main.py        # App instance, /health route
│   ├── tests/
│   └── pyproject.toml
├── frontend/              # React + TypeScript + Vite application
│   ├── src/
│   │   ├── App.tsx
│   │   └── components/
│   └── package.json
├── docs/
│   ├── architecture.md
│   └── decisions/
├── docker-compose.yml     # Local PostgreSQL
├── .env.example
└── .github/workflows/ci.yml
```

## Documentation

- [Architecture Overview](docs/architecture.md)
- [Architecture Decisions](docs/decisions/)
