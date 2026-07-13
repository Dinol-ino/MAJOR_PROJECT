from fastapi import APIRouter
from app.schemas import RecommendRequest, RecommendResponse, RecommendedModel
from app.model.recommend import get_recommendation

router = APIRouter(tags=["recommend"])

@router.post("/recommend", response_model=RecommendResponse)
async def recommend_endpoint(request: RecommendRequest):
    recs = get_recommendation(request.ram_gb, request.vram_gb)
    recommended = [RecommendedModel(model=r["model"], pull=r["pull"]) for r in recs]
    return RecommendResponse(recommended=recommended)
