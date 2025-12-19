from fastapi import FastAPI

from app.routers import health, analyze

app = FastAPI(title="aqua-sense-api")

app.include_router(health.router, prefix="", tags=["health"])
app.include_router(analyze.router, prefix="", tags=["analyze"])


@app.get("/")
async def root():
	return {"service": "aqua-sense-api", "status": "running"}