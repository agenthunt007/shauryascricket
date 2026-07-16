# Shauryas Cricket

Full-stack stats app for the Shauryas cricket team in Houston.

## Architecture

- `backend/`: FastAPI service with SQLModel persistence, stats aggregation, and CricClubs ingestion adapters.
- `frontend/`: React + TypeScript + Vite single-page app for matches, player stats, and series filters.
- Data is organized by league, series, match, player innings, and bowling spells. Raw CricClubs snapshots are stored with every import so parsed records can be audited later.

## Backend

```bash
brew services start postgresql@16
cd backend
python -m venv .venv
source .venv/bin/activate
cp .env.example .env
pip install -r requirements.txt
uvicorn app.main:app --reload
```

API docs are available at `http://127.0.0.1:8000/docs`.

Run backend tests with:

```bash
cd backend
pip install -r requirements-dev.txt
python -m pytest tests
```

Optional environment variables:

```bash
DATABASE_URL=postgresql+psycopg://shauryas:shauryas@localhost:5432/shauryascricket
BACKEND_CORS_ORIGINS=http://localhost:5173
CRICCLUBS_USER_AGENT=ShauryasCricketBot/1.0
```

If the local database has not been created yet:

```bash
psql -h localhost -U postgres -d postgres -c "create role shauryas with login password 'shauryas';"
psql -h localhost -U postgres -d postgres -c "create database shauryascricket owner shauryas;"
```

For development the FastAPI startup hook creates tables in Postgres from the SQLModel metadata. Once the schema is stable, add Alembic migrations before deploying shared production data.

Import public CricClubs scorecards:

```bash
curl -X POST http://127.0.0.1:8000/api/imports/cricclubs \
  -H 'Content-Type: application/json' \
  -d '{
    "league_name": "Houston Cricket League",
    "series_name": "Spring 2026",
    "scorecard_urls": ["https://cricclubs.com/..."]
  }'
```

## Frontend

```bash
cd frontend
npm install
npm run dev
```

The frontend expects the API at `http://127.0.0.1:8000` by default. Override with:

```bash
VITE_API_BASE_URL=http://127.0.0.1:8000 npm run dev
```

## Notes on CricClubs ingestion

CricClubs markup and query parameters can differ by league. The ingestion module is intentionally isolated in `backend/app/ingestion/`:

- `client.py` fetches public pages politely with a team-specific user agent.
- `cricclubs_parser.py` parses scorecard HTML into normalized domain objects.
- `service.py` deduplicates imported matches and stores source snapshots.

If a league uses a different CricClubs scorecard layout, adjust only `cricclubs_parser.py` and add a fixture test.
