import os
import sys
from pathlib import Path
from typing import List, Optional, Dict, Any
from datetime import datetime
import asyncio

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field
from dotenv import load_dotenv

# Load .env.local
current_dir = Path(__file__).resolve().parent
env_path = current_dir.parent.parent / '.env.local'
load_dotenv(dotenv_path=env_path)

MONGO_URI = os.getenv("MONGO_ATLAS_URI")
MONGO_DB_NAME = os.getenv("MONGO_DB", "opencreator")

if not MONGO_URI:
    # Fallback/Error handling
    print("WARNING: MONGO_ATLAS_URI not set.")

app = FastAPI(title="User Profile Analyzer API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

client = AsyncIOMotorClient(MONGO_URI)
db = client[MONGO_DB_NAME]
collection = db["user_workflow_profile"]

# --- Models ---
class WorkflowAnalysis(BaseModel):
    rank: int
    purpose: str
    confidence: str
    reason: str

class Positioning(BaseModel):
    industry: Optional[str] = None
    business_scale: Optional[str] = None
    platform: Optional[str] = None
    content_type: Optional[str] = None

class BusinessPotential(BaseModel):
    score: Optional[int] = None
    stage: Optional[str] = None
    barrier: Optional[str] = None
    recommendation: Optional[str] = None

class AiProfile(BaseModel):
    primary_purpose: Optional[str] = None
    user_type: Optional[str] = None
    user_category: Optional[str] = None  # Added user_category
    activity_level: Optional[str] = None
    content_focus: List[str] = []
    tags: List[str] = []
    summary: Optional[str] = None
    positioning: Optional[Positioning] = None
    business_potential: Optional[BusinessPotential] = None
    workflow_analysis: List[WorkflowAnalysis] = []
    analyzed_at: Optional[datetime] = None
    model: Optional[str] = None

class UserStats(BaseModel):
    total_runs_30d: Optional[int] = 0
    active_days_30d: Optional[int] = 0

class WorkflowNode(BaseModel):
    rank: int
    workflow_name: Optional[str] = None
    signature: Optional[str] = None
    run_count: int
    node_types: List[str] = []
    snapshot_url: Optional[str] = None

class UserProfile(BaseModel):
    id: str = Field(alias="_id")
    user_id: str
    user_email: Optional[str] = None
    stats: Optional[UserStats] = None
    ai_profile: Optional[AiProfile] = None
    top_workflows: List[WorkflowNode] = []
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        populate_by_name = True

class PaginatedResponse(BaseModel):
    total: int
    page: int
    limit: int
    items: List[UserProfile]

@app.on_event("startup")
async def startup_db_client():
    try:
        await client.admin.command('ping')
        print("Connected to MongoDB!")
    except Exception as e:
        print(f"Connection failed: {e}")

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()

# --- Routes ---

@app.get("/api/users", response_model=PaginatedResponse)
async def list_users(
    page: int = 1,
    limit: int = 50,
    industry: Optional[str] = None,
    platform: Optional[str] = None,
    stage: Optional[str] = None,
    category: Optional[str] = None,  # Added category param
    min_score: Optional[int] = Query(None),
    sort_by: str = "business_potential.score",
    sort_order: str = "desc"
):
    query = {}
    if industry: query["ai_profile.positioning.industry"] = industry
    if platform: query["ai_profile.positioning.platform"] = platform
    if stage: query["ai_profile.business_potential.stage"] = stage
    if category: query["ai_profile.user_category"] = category
    if min_score is not None: query["ai_profile.business_potential.score"] = {"$gte": min_score}

    skip = (page - 1) * limit
    
    sort_field = "ai_profile.business_potential.score"
    if sort_by == "stats.active_days_30d":
        sort_field = "stats.active_days_30d"
    
    sort_dir = -1 if sort_order == "desc" else 1

    total = await collection.count_documents(query)
    cursor = collection.find(query).sort(sort_field, sort_dir).skip(skip).limit(limit)
    users = await cursor.to_list(length=limit)
    
    for u in users: u["_id"] = str(u["_id"])
    return {"total": total, "page": page, "limit": limit, "items": users}

# ... (get_user and get_stats remain unchanged)

@app.get("/api/filters")
async def get_filters():
    industries = await collection.distinct("ai_profile.positioning.industry")
    platforms = await collection.distinct("ai_profile.positioning.platform")
    stages = await collection.distinct("ai_profile.business_potential.stage")
    categories = await collection.distinct("ai_profile.user_category") # Added categories
    
    return {
        "industries": sorted([x for x in industries if x]),
        "platforms": sorted([x for x in platforms if x]),
        "stages": sorted([x for x in stages if x]),
        "categories": sorted([x for x in categories if x])
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
