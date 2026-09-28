from pydantic_settings import BaseSettings
from typing import List
import json

class Settings(BaseSettings):
    DATABASE_URL: str
    REDIS_URL: str
    
    S3_ENDPOINT: str
    S3_ACCESS_KEY: str
    S3_SECRET_KEY: str
    S3_BUCKET_RAW: str
    S3_BUCKET_INTERMEDIATE: str
    S3_BUCKET_PRODUCTS: str
    
    CDSE_CLIENT_ID: str
    CDSE_CLIENT_SECRET: str
    
    API_PORT: int = 8000
    CORS_ORIGINS: List[str] = ["http://localhost:5173"]

    class Config:
        env_file = "../../.env"
        extra = "ignore"

settings = Settings()
