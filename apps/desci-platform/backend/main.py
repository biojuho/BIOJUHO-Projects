"""
DeSci Platform - Backend API
Built with FastAPI by Raph & JuPark
"""
import os
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from auth import get_current_user

load_dotenv()

app = FastAPI(
    title="DSCI-DecentBio",
    description="Decentralized Science Platform API",
    version="0.1.0"
)

# CORS 설정 - 환경변수에서 읽기
allowed_origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:5173").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    """Public endpoint"""
    return {"message": "Hello DeSci! This is the beginning of open science."}


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "platform": "DeSci"}


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
