from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def health_check():
	return {"status": "ok"}


@router.get("/health/ping")
async def ping():
	return {"ping": "pong"}