# Dev

TODO: Add development run instructions.

Local development with Docker Compose:

1. Build and start services:

```bash
docker compose up --build
```

2. Wait for API and web health (examples):

```bash
./scripts/wait-for-api.sh http://localhost:8000/health 60
./scripts/wait-for-api.sh http://localhost:3000/health 30
```

3. Open the frontend at http://localhost:3000 and API docs at http://localhost:8000/docs