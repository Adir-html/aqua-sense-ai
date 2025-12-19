# API

How to run (local with Docker):

1. Ensure `.env.example` is present and copied to `.env` if needed.
2. From the repo root run:

```bash
docker compose up --build api
```

The API will be available at http://localhost:8000 and the OpenAPI docs at `/docs`.

TODO:

- [ ] Implement `analyze` endpoint placeholder (`app/routers/analyze.py`).
- [ ] Wire AI inference (can run inside this container for MVP).
- [ ] Add storage and authentication as needed.

Health checks / readiness:

- A small health-check script is available at `scripts/wait-for-api.sh` (POSIX) and `scripts/wait-for-api.ps1` (PowerShell).
- Docker Compose includes a container-level healthcheck for the `api` service that probes `/health`.

Usage example (wait until API is ready):

```bash
./scripts/wait-for-api.sh http://localhost:8000/health 60
```