# Homelab Parts Finder

A PCPartPicker-style tool for homelab and server hardware, including used parts.
PCPartPicker doesn't cover server parts, mini PCs, or used listings; this fills that gap.

## Core features (MVP)
- Auth (signup/login).
- Build flow: choose **prebuilt** (mini PCs, used office PCs, servers like Dell R730/T340) or **custom build**. Rack selection is optional and only offered when relevant.
- **Power cost calculator**: servers run 24/7, so show estimated idle and load wattage as a *range* (TDP is not real draw) and convert to cost using a user-entered electricity rate (default by region). Label as estimates.
- **Used listings with price history**: plot price range + history per part.
- **Risk slider**: hide listings above a risk threshold. Rule-based and explainable first (show *why* a listing is flagged). Signals: seller feedback score/count, account age, price far below median, "untested / as-is / for parts" keywords, stock photos only.
- **Compatibility warnings and advice**: e.g. RDIMM vs UDIMM, CPU socket, BIOS version for newer CPUs, vendor-locked parts, "run SMART/badblocks on used drives".

## Later (not MVP)
- AI-assisted matching of messy listings to catalog parts (v2).
- Custom-build compatibility rules engine at full depth (v2).
- Rack planning, drag-and-drop service planner (React Flow) for Docker/K8s/Plex, crowd-sourced idle power data (v3).
- Keep scope to homelab/server parts. Do not generalize to all electronics.

## Stack
- **Frontend:** React + TypeScript
- **API:** Python, FastAPI
- **DB:** Supabase Postgres, accessed via SQLAlchemy (2.x) with Alembic migrations. No Prisma.
- **Ingestion workers:** Python (eBay Browse API first; Playwright/BeautifulSoup only where terms allow), run as background jobs via arq or Celery.
- **Cache/queue:** Redis
- **Testing/CI:** pytest, GitHub Actions

## Architecture decisions
- **Store a canonical parts catalog** with normalized specs (socket, DDR gen, RDIMM/UDIMM, capacity, speed, PSU form factor, etc.) for supported categories only. Compatibility checks run against catalog specs, never raw listing titles.
- **Store listing/price snapshots** periodically, linked to catalog parts. Price history depends on this.
- **Scraping never runs inside an API request.** Workers write to the DB; the API reads from it.
- Cache external API responses in Redis to respect rate limits.
- Prefer official APIs over scraping; respect site terms of service.

## MVP milestone
1. Repo scaffold: `frontend/`, `backend/` (FastAPI), `worker/`, docker-compose for local Postgres + Redis.
2. Auth.
3. Catalog schema + seed data for a few prebuilts, CPUs, and RAM.
4. eBay ingestion worker for those categories + price snapshots.
5. Price history chart, power-cost calculator, basic risk flags.
6. Tests + CI, then deploy publicly.

## Conventions
- Type hints everywhere in Python; Pydantic models for API schemas.
- Every schema change goes through an Alembic migration.
- Write tests alongside new backend features.