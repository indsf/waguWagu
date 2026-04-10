import os
os.environ["TOKENIZERS_PARALLELISM"] = "false"

import time
import random
from concurrent.futures import ThreadPoolExecutor, as_completed

from fastapi import FastAPI, HTTPException, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn

from feedback_system import feedback_manager
from crawler import naver_blog_search, fetch_many_blog_htmls, cleanup_cache, cache_info
from classifier import load_kobert_model, predict_text_raw_prob, process_blog_content_sync

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

executor = ThreadPoolExecutor(max_workers=4)


@app.get("/health")
async def health_check():
    return {"status": "ok", "message": "서버가 정상 작동 중입니다."}


@app.post("/api/warmup")
async def warmup_models():
    try:
        load_kobert_model()
        predict_text_raw_prob("테스트 텍스트")
        return {"status": "ok", "message": "광고 판별 모델이 준비되었습니다."}
    except Exception as e:
        return {"status": "error", "message": f"모델 워밍업 중 오류 발생: {str(e)}"}


@app.get("/api/cache_info")
async def get_cache_info():
    cleanup_cache()
    return cache_info()


@app.post("/api/crawl_predict", response_class=JSONResponse)
async def crawl_predict_json(query: str = Form(...)):
    if not query or not query.strip():
        raise HTTPException(status_code=400, detail="query가 비어 있습니다.")

    start_time = time.time()

    # 1. 네이버 블로그 검색
    search_results = naver_blog_search(query, "sim_random")
    if not search_results:
        return JSONResponse(status_code=200, content={"status": "ok", "data": []})

    # 2. HTML은 비동기로 한 번에 수집
    blog_data = await fetch_many_blog_htmls(search_results)

    # 3. 광고 판별/OCR은 CPU 작업이므로 스레드풀에서 처리
    futures = []
    for title, link, html in blog_data:
        future = executor.submit(process_blog_content_sync, title, link, html)
        futures.append(future)

    final = []
    for future in as_completed(futures):
        try:
            result = future.result(timeout=30)
            final.append(result)
        except Exception:
            continue

    # 4. 사용자 피드백 점수 반영
    blog_rating_stats = feedback_manager.get_blog_average_ratings()
    for result in final:
        blog_url = result.get("link", "")
        blog_stats = blog_rating_stats.get(blog_url, {})
        result["recommendation_count"] = blog_stats.get("recommendation_count", 0)
        result["average_rating"] = blog_stats.get("average_rating", 0)
        result["total_ratings"] = blog_stats.get("total_ratings", 0)

    # 5. 추천 블로그 우선 정렬
    time_seed = int(time.time() * 1000) % 10000
    random.seed(time_seed)

    recommended_blogs = []
    other_blogs = []
    for result in final:
        if result.get("recommendation_count", 0) > 0:
            recommended_blogs.append(result)
        else:
            other_blogs.append(result)

    recommended_blogs.sort(
        key=lambda x: (-x["recommendation_count"], -x["average_rating"], x["ad_probability"])
    )
    top_recommended = recommended_blogs[:3]
    other_blogs.extend(recommended_blogs[3:])
    random.shuffle(other_blogs)
    final = top_recommended + other_blogs

    total_time = time.time() - start_time
    print(f"✅ 전체 처리 완료: {total_time:.2f}초 ({len(final)}개 결과)")

    return JSONResponse(status_code=200, content={"status": "ok", "data": final})


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8013)
