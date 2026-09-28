from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .config import settings
from .api import aoi

app = FastAPI(
    title="Sentinel Deformation Monitor",
    description="API for managing Sentinel-1 InSAR processing and deformation monitoring",
    version="0.1.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def health_check():
    return {"status": "ok", "service": "Sentinel Deformation Monitor API"}

app.include_router(aoi.router, prefix="/api/aois", tags=["aois"])
