"""
메인 실행 파일 - 모든 시스템을 통합하여 FastAPI 서버 실행
"""

import asyncio
from fastapi import FastAPI, HTTPException, Form
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# 분리된 모듈들 import
from blog_crawler import naver_blog_search, crawl_blogs_async
from ad_classifier import load_kobert_model, predict_text_raw_prob
from sentiment_analyzer import load_kobart_model, generate_kobart_summary
from restaurant_service import get_restaurant_detail, search_restaurants
from feedback_system import (
    feedback_manager, 
    create_ad_feedback, 
    create_restaurant_feedback,
    create_search_feedback
)

# ─────────────────────────────────────────────────────────────────────────────
# FastAPI 앱 설정
# ─────────────────────────────────────────────────────────────────────────────
app = FastAPI(title="Mukabolrae API", version="1.0.0")

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─────────────────────────────────────────────────────────────────────────────
# 헬스체크 및 모델 워밍업 엔드포인트
# ─────────────────────────────────────────────────────────────────────────────
@app.get("/health")
async def health_check():
    """서버 상태 확인"""
    return {"status": "ok", "message": "서버가 정상 작동 중입니다."}

@app.post("/api/warmup")
async def warmup_models():
    """모델들을 미리 로딩하여 첫 요청 지연시간 감소"""
    try:
        print("🔥 모델 워밍업 시작...")
        
        # KoBERT 워밍업
        load_kobert_model()
        predict_text_raw_prob("테스트 텍스트")
        
        # KoBART 워밍업  
        load_kobart_model()
        generate_kobart_summary("테스트 리뷰 내용입니다.", max_length=50)
        
        print("✅ 모델 워밍업 완료!")
        return {"status": "ok", "message": "모든 모델이 준비되었습니다."}
    except Exception as e:
        print(f"❌ 모델 워밍업 실패: {e}")
        return {"status": "error", "message": f"모델 워밍업 중 오류 발생: {str(e)}"}

# ─────────────────────────────────────────────────────────────────────────────
# 맛집 정보 API 엔드포인트
# ─────────────────────────────────────────────────────────────────────────────
@app.get("/api/restaurant/{name}", response_class=JSONResponse)
async def restaurant_detail(name: str):
    """맛집 상세 정보 조회"""
    try:
        result = get_restaurant_detail(name)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"서버 오류: {str(e)}")

@app.get("/api/restaurants/search")
async def search_restaurants_api(q: str):
    """맛집 검색"""
    try:
        results = search_restaurants(q)
        return {"results": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"검색 중 오류: {str(e)}")

# ─────────────────────────────────────────────────────────────────────────────
# 블로그 검색 및 분석 API 엔드포인트  
# ─────────────────────────────────────────────────────────────────────────────
@app.post("/api/search")
async def search_blogs(query: str = Form(...)):
    """블로그 검색 및 광고 판별"""
    try:
        print(f"🔍 검색 요청: {query} (전략: {search_strategy})")
        
        # 1단계: 네이버 블로그 검색
        blog_list = naver_blog_search(query, search_strategy)
        if not blog_list:
            return {
                "query": query,
                "total_results": 0,
                "results": [],
                "message": "검색 결과가 없습니다."
            }
        
        # 2단계: 비동기 크롤링 및 분석
        results = await crawl_blogs_async(blog_list)
        
        # 3단계: 광고 확률 순으로 정렬 (낮은 순서 = 비광고 우선)
        results.sort(key=lambda x: x["ad_probability"])
        
        # 검색 피드백 생성 (비동기)
        asyncio.create_task(create_search_feedback(
            query=query,
            total_results=len(results),
            strategy_used=search_strategy
        ))
        
        return {
            "query": query,
            "total_results": len(results),
            "results": results[:18],  # 최대 18개 반환
            "search_strategy": search_strategy
        }
        
    except Exception as e:
        print(f"❌ 검색 중 오류: {e}")
        raise HTTPException(status_code=500, detail=f"검색 중 오류가 발생했습니다: {str(e)}")

# ─────────────────────────────────────────────────────────────────────────────
# 피드백 API 엔드포인트
# ─────────────────────────────────────────────────────────────────────────────
@app.post("/api/feedback/ad")
async def submit_ad_feedback(
    blog_url: str = Form(...),
    blog_title: str = Form(...),
    predicted_probability: float = Form(...),
    is_correct: bool = Form(...),
    user_comment: str = Form("")
):
    """광고 판별 피드백 제출"""
    try:
        feedback_id = await create_ad_feedback(
            blog_url=blog_url,
            blog_title=blog_title,
            predicted_probability=predicted_probability,
            is_correct=is_correct,
            user_comment=user_comment
        )
        return {"status": "success", "feedback_id": feedback_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"피드백 저장 실패: {str(e)}")

@app.post("/api/feedback/restaurant")
async def submit_restaurant_feedback(
    restaurant_name: str = Form(...),
    rating: int = Form(...),
    visited: bool = Form(...),
    comment: str = Form("")
):
    """맛집 평가 피드백 제출"""
    try:
        feedback_id = await create_restaurant_feedback(
            restaurant_name=restaurant_name,
            rating=rating,
            visited=visited,
            comment=comment
        )
        return {"status": "success", "feedback_id": feedback_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"피드백 저장 실패: {str(e)}")

@app.get("/api/feedback/stats")
async def get_feedback_stats():
    """피드백 통계 조회"""
    try:
        stats = feedback_manager.get_stats()
        return stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"통계 조회 실패: {str(e)}")

@app.get("/api/feedback/analytics")
async def get_feedback_analytics():
    """피드백 분석 데이터 조회"""
    try:
        analytics = feedback_manager.get_analytics()
        return analytics
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"분석 데이터 조회 실패: {str(e)}")

# ─────────────────────────────────────────────────────────────────────────────
# 메인 실행부
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("🚀 Mukabolrae 서버 시작...")
    print("📍 서버 주소: http://localhost:8013")
    print("📖 API 문서: http://localhost:8013/docs")
    
    uvicorn.run(
        "main:app",  # import string으로 변경
        host="0.0.0.0",
        port=8013,
        reload=True,  # 개발 시에만 사용
        access_log=True
    )