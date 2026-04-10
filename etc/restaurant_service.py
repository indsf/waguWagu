"""
맛집 정보 관련 모듈
- 맛집 데이터베이스 접근
- 맛집 이름 추출 및 매칭
- 맛집 정보 조회 및 반환
"""

import re
from typing import Optional, Dict, Any
from rapidfuzz import fuzz

from data import restaurant_db, restaurant_aliases
from sentiment_analyzer import (
    get_hashtags_and_score, 
    compute_percentile, 
    compute_ratio_text,
    get_review_text_from_db,
    split_into_sentences,
    categorize_sentences,
    generate_kobart_summary
)

def clean_text(text: str) -> str:
    """텍스트 정리 (HTML 태그 및 특수문자 제거)"""
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"[\"'''""()\[\]{}]", "", text)
    text = re.sub(r"[^가-힣a-zA-Z0-9\s]", " ", text)
    return text.strip()

def fuzzy_extract_restaurant_name(title: str, text: str) -> Optional[str]:
    """제목과 본문에서 맛집 이름을 퍼지 매칭으로 추출"""
    full_raw = clean_text(title + " " + text)
    full = full_raw.replace(" ", "")
    best_name, best_score = None, 0
    
    for name, aliases in restaurant_aliases.items():
        candidates = [name] + aliases
        for alias in candidates:
            alias_nospace = alias.replace(" ", "")
            score_val = fuzz.partial_ratio(alias_nospace, full)
            if score_val > best_score and score_val >= 60:
                best_name, best_score = name, score_val
    
    return best_name

def get_restaurant_info(name: str) -> Optional[Dict[str, Any]]:
    """맛집 기본 정보 조회"""
    return restaurant_db.get(name)

def get_restaurant_detail(name: str) -> Dict[str, Any]:
    """맛집 상세 정보 조회 (감성 분석 포함)"""
    info = restaurant_db.get(name)
    if not info:
        raise ValueError(f"'{name}'에 대한 정보가 없습니다.")

    # 감성 분석 데이터 조회
    pos_tags_all, neg_tags_all, score = get_hashtags_and_score(name)
    sentiment_percentile = compute_percentile(score)
    sentiment_ratio = compute_ratio_text(score)

    # 리뷰 텍스트 조회 및 처리
    review_content = get_review_text_from_db(name)
    
    if review_content:
        sentences = split_into_sentences(review_content)
        pos_sents, neg_sents = categorize_sentences(sentences)
        
        # 요약 생성
        summary_text = generate_kobart_summary(
            " ".join(sentences[:20]),  # 처음 20문장만 사용
            max_length=100
        )
    else:
        pos_sents, neg_sents = [], []
        summary_text = "리뷰 데이터가 없습니다."

    return {
        "name": name,
        "info": info,
        "hashtags": {
            "positive": pos_tags_all[:5] if len(pos_tags_all) > 5 else pos_tags_all,
            "negative": neg_tags_all[:5] if len(neg_tags_all) > 5 else neg_tags_all
        },
        "sentiment": {
            "score": round(score, 2),
            "percentile": round(sentiment_percentile, 1),
            "comparison": sentiment_ratio
        },
        "reviews": {
            "positive_sentences": pos_sents[:3],  # 상위 3개만
            "negative_sentences": neg_sents[:3],  # 상위 3개만
            "summary": summary_text
        }
    }

def search_restaurants(query: str) -> list:
    """맛집 이름으로 검색"""
    query_clean = query.replace(" ", "").lower()
    results = []
    
    for name, aliases in restaurant_aliases.items():
        # 정확한 매치 체크
        candidates = [name] + aliases
        for candidate in candidates:
            candidate_clean = candidate.replace(" ", "").lower()
            if query_clean in candidate_clean or candidate_clean in query_clean:
                if name not in [r["name"] for r in results]:
                    info = restaurant_db.get(name, {})
                    results.append({
                        "name": name,
                        "category": info.get("category", ""),
                        "address": info.get("address", "")
                    })
                break
    
    # 퍼지 매칭으로 추가 검색
    if len(results) < 5:
        for name in restaurant_db.keys():
            if name not in [r["name"] for r in results]:
                score = fuzz.partial_ratio(query_clean, name.replace(" ", "").lower())
                if score >= 70:
                    info = restaurant_db.get(name, {})
                    results.append({
                        "name": name,
                        "category": info.get("category", ""),
                        "address": info.get("address", "")
                    })
    
    return results[:10]  # 최대 10개만 반환

def get_all_restaurants() -> list:
    """모든 맛집 목록 조회"""
    return [
        {
            "name": name,
            "category": info.get("category", ""),
            "address": info.get("address", "")
        }
        for name, info in restaurant_db.items()
    ]