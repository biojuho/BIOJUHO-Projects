"""
DeSci Platform - Backend API
Built with FastAPI by Raph & JuPark
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="BioJuho DeSci Platform",
    description="Decentralized Science Platform API",
    version="0.1.0"
)

# CORS 설정 (프론트엔드 연결용)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Vite 기본 포트
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return {"message": "Hello DeSci! This is the beginning of open science."}

@app.get("/health")
async def health_check():
    return {"status": "healthy", "platform": "DeSci"}
