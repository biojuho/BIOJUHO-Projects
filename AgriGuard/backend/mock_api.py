from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from typing import Dict, Any

app = FastAPI(title="AgriGuard Mock API", version="0.1.0")

# Allow CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/v1/dashboard/summary", response_model=Dict[str, Any])
async def get_dashboard_summary():
    """
    Mock data API for the frontend dashboard initialization.
    """
    return {
        "status": "success",
        "data": {
            "total_farms": 142,
            "active_sensors": 450,
            "critical_alerts": 3,
            "growth_cycles": {
                "active": 25,
                "completed": 102
            },
            "recent_activity": [
                {"timestamp": "2026-02-24T09:00:00Z", "event": "Sensor A1 reported low moisture"},
                {"timestamp": "2026-02-24T08:30:00Z", "event": "Fertilizer applied to Grid B2"}
            ]
        }
    }

@app.get("/api/v1/fields/status", response_model=Dict[str, Any])
async def get_fields_status():
    """
    Mock data API for detailed field views.
    """
    return {
        "status": "success",
        "data": [
            {"id": "F-001", "name": "North Field", "crop": "Corn", "health": "Good", "moisture_level": 45.2},
            {"id": "F-002", "name": "East Field", "crop": "Soybeans", "health": "Warning", "moisture_level": 22.1}
        ]
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
