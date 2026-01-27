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
class WorkflowEdge(BaseModel):
    id: str
    source: str
    target: str
    sourceHandle: Optional[str] = None
    targetHandle: Optional[str] = None

class WorkflowNodeData(BaseModel):
    label: Optional[str] = None
    prompt: Optional[str] = None
    selectedModels: Optional[List[str]] = None
    # Add other data fields as permitted loosely to prevent validation errors on varied node types
    class Config:
        extra = "allow"

class GraphNode(BaseModel):
    id: str
    type: str
    label: Optional[str] = None
    isInputNode: Optional[bool] = False
    data: Optional[Dict[str, Any]] = None

class WorkflowTopology(BaseModel):
    nodes: List[GraphNode] = []
    edges: List[WorkflowEdge] = []

class WorkflowAnalysis(BaseModel):
    category: Optional[str] = None
    subcategory: Optional[str] = None
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
    user_category: Optional[str] = None
    user_subcategory: Optional[str] = None
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
    total_runs: Optional[int] = 0
    active_days: Optional[int] = 0
    period: Optional[str] = None
    # Backward compatibility if needed
    total_runs_30d: Optional[int] = Field(None, alias="total_runs")
    active_days_30d: Optional[int] = Field(None, alias="active_days")

class PaymentStats(BaseModel):
    paid_count: int = 0
    unpaid_count: int = 0
    is_paid_user: bool = False
    has_payment_intent: bool = False
    updated_at: Optional[datetime] = None

class WorkflowNode(BaseModel):
    rank: int
    flow_id: Optional[str] = None
    flow_task_id: Optional[str] = None
    workflow_name: Optional[str] = None
    run_count: int
    snapshot_url: Optional[str] = None
    topology: Optional[WorkflowTopology] = None
    # Keep legacy fields optional to avoid breakage if data mixed
    signature: Optional[str] = None
    node_types: List[str] = []

class UserProfile(BaseModel):
    id: str = Field(alias="_id")
    user_id: str
    user_email: Optional[str] = None
    stats: Optional[UserStats] = None
    payment_stats: Optional[PaymentStats] = None
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

# --- Routes ---

@app.get("/api/users", response_model=PaginatedResponse)
async def list_users(
    page: int = 1,
    limit: int = 50,
    industry: Optional[str] = None,
    platform: Optional[str] = None,
    stage: Optional[str] = None,
    category: Optional[str] = None,
    min_score: Optional[int] = Query(None),
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    sort_by: str = "business_potential.score",
    sort_order: str = "desc"
):
    query = {}
    if industry: query["ai_profile.positioning.industry"] = industry
    if platform: query["ai_profile.positioning.platform"] = platform
    if stage: query["ai_profile.business_potential.stage"] = stage
    if category: query["ai_profile.user_category"] = category
    if min_score is not None: query["ai_profile.business_potential.score"] = {"$gte": min_score}

    # Time Filter
    date_filter = {}
    if start_date:
        date_filter["$gte"] = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
    if end_date:
        date_filter["$lte"] = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
    
    if date_filter:
        query["updated_at"] = date_filter

    skip = (page - 1) * limit
    
    sort_field = "ai_profile.business_potential.score"
    if sort_by == "stats.active_days":
        sort_field = "stats.active_days"
    
    sort_dir = -1 if sort_order == "desc" else 1

    total = await collection.count_documents(query)
    cursor = collection.find(query).sort(sort_field, sort_dir).skip(skip).limit(limit)
    users = await cursor.to_list(length=limit)
    
    for u in users: u["_id"] = str(u["_id"])
    return {"total": total, "page": page, "limit": limit, "items": users}

@app.get("/api/users/{user_id}", response_model=UserProfile)
async def get_user(user_id: str):
    user = await collection.find_one({"user_id": user_id})
    if not user: raise HTTPException(404, "User not found")
    user["_id"] = str(user["_id"])
    return user

@app.get("/api/stats")
@app.get("/api/stats")
async def get_stats(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    category: Optional[str] = None
):
    # Base match with time filter
    params_match = {}
    
    if start_date or end_date:
        date_filter = {}
        if start_date:
            date_filter["$gte"] = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
        if end_date:
            date_filter["$lte"] = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
        if date_filter:
            params_match["updated_at"] = date_filter
            
    # Apply global category filter to existing match
    if category:
        params_match["ai_profile.user_category"] = category

    pipeline_industry = [
        {"$match": {**params_match, "ai_profile.positioning.industry": {"$ne": "无法判断"}}},
        {"$group": {"_id": "$ai_profile.positioning.industry", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}}
    ]
    pipeline_stage = [
        {"$match": {**params_match, "ai_profile.business_potential.stage": {"$ne": "无法判断"}}},
        {"$group": {"_id": "$ai_profile.business_potential.stage", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}}
    ]
    # For category distribution, if a category is selected, we might still want to show all categories 
    # to let user switch, OR we show subcategories. 
    # The user logic is "click Pie -> Filter Everything". Usually Pie itself remains as "Navigation".
    # But if we strictly filter params_match, the pie chart would become 100% the selected category.
    # To avoid this "disappearing options" effect, we will compute the "Category Pie" WITHOUT the category filter,
    # UNLESS the user explicitly wants to drill down.
    # Actually, the requirement says "Subcategory Analytics" is already drill-down. 
    # Let's keep Category Pie independent of the 'category' filter (except for time), 
    # so it acts as the controller.
    
    # Correction: The params_match includes 'category' now. 
    # We must separate "global filter metrics" (like industry, stats) from "distribution metrics" (the pie itself).
    
    # 1. Stats and Charts Filtered by Category
    industries = await collection.aggregate(pipeline_industry).to_list(None)
    
    # 2. Category Distribution (Pie Chart) - SHOULD NOT be filtered by category (unless drilldown logic handles it).
    # However, for now, let's keep the Pie Chart showing ALL categories (just time filtered) 
    # so the user can see proportions and click others.
    
    pie_match = params_match.copy()
    if category: 
        del pie_match["ai_profile.user_category"] # Remove category filter for the Pie Chart data source
        
    pipeline_category = [
        {"$match": {**pie_match, "ai_profile.user_category": {"$exists": True, "$ne": None}}},
        {
            "$group": {
                "_id": {
                    "category": "$ai_profile.user_category",
                    "subcategory": "$ai_profile.user_subcategory"
                },
                "count": {"$sum": 1}
            }
        },
        {"$sort": {"count": -1}}
    ]
    categories_raw = await collection.aggregate(pipeline_category).to_list(None)
    
    # 3. Payment Stats by Category (for the new Chart)
    # If category selected: Breakdown by SUBCATEGORY
    # If no category: Breakdown by CATEGORY
    
    if category:
        # Drill down mode
        pipeline_payment = [
            {"$match": {**params_match, "ai_profile.user_subcategory": {"$exists": True}}}, # Use params_match to respect the category filter
            {
                "$group": {
                    "_id": "$ai_profile.user_subcategory",
                    "total": {"$sum": 1},
                    "paid": {"$sum": {"$cond": [{"$eq": ["$payment_stats.is_paid_user", True]}, 1, 0]}}
                }
            }
        ]
    else:
        # Overview mode
        pipeline_payment = [
            {"$match": {**pie_match, "ai_profile.user_category": {"$exists": True, "$ne": None}}},
            {
                "$group": {
                    "_id": "$ai_profile.user_category",
                    "total": {"$sum": 1},
                    "paid": {"$sum": {"$cond": [{"$eq": ["$payment_stats.is_paid_user", True]}, 1, 0]}}
                }
            }
        ]
        
    payment_raw = await collection.aggregate(pipeline_payment).to_list(None)

    # Process categories into a nested structure
    categories_data = {}
    for item in categories_raw:
        cat = item["_id"].get("category")
        sub = item["_id"].get("subcategory") or "Unknown"
        count = item["count"]
        
        if cat not in categories_data:
            categories_data[cat] = {"count": 0, "subcategories": {}}
        
        categories_data[cat]["count"] += count
        categories_data[cat]["subcategories"][sub] = count
        
    # Process payment stats
    payment_stats = {}
    for item in payment_raw:
        key = item["_id"] or "Unknown"
        total = item["total"]
        paid = item["paid"]
        rate = round((paid / total) * 100, 1) if total > 0 else 0
        payment_stats[key] = {"total": total, "paid": paid, "rate": rate}
    
    high_potential = await collection.count_documents({**params_match, "ai_profile.business_potential.score": {"$gte": 7}})
    total_users = await collection.count_documents(params_match)
    
    stages = await collection.aggregate(pipeline_stage).to_list(None)

    return {
        "industries": {i["_id"]: i["count"] for i in industries if i["_id"]},
        "stages": {i["_id"]: i["count"] for i in stages if i["_id"]},
        "categories": categories_data,
        "payment_stats": payment_stats,
        "high_potential_count": high_potential,
        "total_users": total_users
    }

@app.get("/api/filters")
async def get_filters():
    industries = await collection.distinct("ai_profile.positioning.industry")
    platforms = await collection.distinct("ai_profile.positioning.platform")
    stages = await collection.distinct("ai_profile.business_potential.stage")
    categories = await collection.distinct("ai_profile.user_category")
    
    return {
        "industries": sorted([x for x in industries if x]),
        "platforms": sorted([x for x in platforms if x]),
        "stages": sorted([x for x in stages if x]),
        "categories": sorted([x for x in categories if x])
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
