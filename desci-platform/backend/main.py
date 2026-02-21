"""
DeSci Platform - Backend API
Built with FastAPI by Raph & JuPark
"""
import os
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from auth import get_current_user
from database import Base, engine
from routers import programs, tasks, deliverables, audit, orchestrations

load_dotenv()

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Regulatory Collaboration MVP",
    description="Regulatory-first collaboration platform API",
    version="0.1.0",
)

# CORS 설정 - 환경변수에서 읽기
allowed_origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(programs.router)
app.include_router(tasks.router)
app.include_router(deliverables.router)
app.include_router(audit.router)
app.include_router(orchestrations.router)


@app.get("/")
async def root():
    """Public endpoint"""
    return {"message": "Regulatory collaboration MVP API is running."}


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "platform": "Regulatory Collaboration MVP"}


@app.get("/me")
async def get_me(user: dict = Depends(get_current_user)):
    """
    Protected endpoint - requires valid Firebase token
    Returns authenticated user information
    """
    return {
        "uid": user.get("uid"),
        "email": user.get("email"),
        "name": user.get("name"),
        "picture": user.get("picture"),
    }
