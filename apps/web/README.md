# Web App

How to run (local with Docker):

1. Ensure `.env.example` is present and copied to `.env` if needed.
2. From the repo root run:

```bash
docker compose up --build web
```

Then open http://localhost:3000

TODO:

- [ ] Implement upload UI (`src/upload.html`, `src/js/upload.js`)
- [ ] Implement results page (`src/results.html`, `src/js/results.js`)
- [ ] Add static assets and tests

Verify web health:

- The web container exposes a simple health page at `/health` which returns HTTP 200 with body `OK`.
- To check locally:

```bash
curl -i http://localhost:3000/health
```

- Or use the included script to wait for readiness:

```bash
./scripts/wait-for-api.sh http://localhost:3000/health 30
```