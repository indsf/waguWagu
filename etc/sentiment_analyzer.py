"""
감성 분석 관련 모듈
- KoBART 모델을 이용한 텍스트 요약
- 긍정/부정 키워드 기반 감성 분석
- 해시태그 및 감성점수 처리
"""

import os
import re
import ast
import pandas as pd
import torch
from typing import Tuple, List
from kiwipiepy import Kiwi
from transformers import (
    BartForConditionalGeneration,
    PreTrainedTokenizerFast
)

from config import (
    POSITIVE_KEYWORDS,
    NEGATIVE_KEYWORDS,
    MODEL_CACHE_DIR
)

# 디바이스 설정
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

# 전역 모델 변수들
kobart_model = None
kobart_tokenizer = None

# Kiwi tokenizer
kiwi = Kiwi()

# CSV 데이터 로드
this_dir = os.path.dirname(__file__)
sentiment_csv_path = os.path.join(this_dir, "store_sentiment_result.csv")
reviews_csv_path = os.path.join(this_dir, "processed_reviews.csv")

# 감성 점수 데이터 로드
if os.path.isfile(sentiment_csv_path):
    hashtag_df = pd.read_csv(sentiment_csv_path)
    all_scores = hashtag_df["감성점수"].astype(float)
    avg_all_score = float(all_scores.mean())
else:
    hashtag_df = pd.DataFrame()
    all_scores = pd.Series()
    avg_all_score = 0.0
    print(f"⚠️ 감성점수 CSV 파일이 없습니다: {sentiment_csv_path}")

# 리뷰 데이터 로드
if os.path.isfile(reviews_csv_path):
    df_reviews = pd.read_csv(reviews_csv_path)
else:
    df_reviews = pd.DataFrame()
    print(f"⚠️ 리뷰 CSV 파일이 없습니다: {reviews_csv_path}")

def load_kobart_model():
    """KoBART 모델을 지연 로딩"""
    global kobart_model, kobart_tokenizer
    if kobart_model is not None:
        return kobart_model, kobart_tokenizer
        
    print("📚 KoBART 모델 로딩 시작...")
    try:
        # 로컬 캐시 활용
        kobart_tokenizer = PreTrainedTokenizerFast.from_pretrained(
            "EbanLee/kobart-summary-v3",
            cache_dir=MODEL_CACHE_DIR  # 로컬 캐시 디렉토리 설정
        )
        kobart_model = BartForConditionalGeneration.from_pretrained(
            "EbanLee/kobart-summary-v3",
            cache_dir=MODEL_CACHE_DIR  # 로컬 캐시 디렉토리 설정
        ).to(DEVICE)
        kobart_model.eval()
        
        # 메모리 최적화
        if hasattr(torch.backends, 'cudnn'):
            torch.backends.cudnn.benchmark = True
            
        print("✅ KoBART 요약 모델 로드 완료")
        return kobart_model, kobart_tokenizer
    except Exception as e:
        raise RuntimeError(f"KoBART 모델 로드 중 오류 발생: {e}")

def get_hashtags_and_score(name: str) -> Tuple[List, List, float]:
    """맛집 이름으로 해시태그와 감성점수 조회"""
    if hashtag_df.empty:
        return [], [], 0.0
        
    row = hashtag_df[hashtag_df["store_name"] == name]
    if row.empty:
        return [], [], 0.0
    try:
        pos_list = ast.literal_eval(row.iloc[0]["긍정해시태그"])
    except:
        pos_list = []
    try:
        neg_list = ast.literal_eval(row.iloc[0]["부정해시태그"])
    except:
        neg_list = []
    score = float(row.iloc[0]["감성점수"])
    return pos_list, neg_list, score

def compute_percentile(score: float) -> float:
    """감성점수의 백분위 계산"""
    if all_scores.empty:
        return 0.0
    rank_pct = (all_scores <= score).sum() / len(all_scores) * 100
    return float(rank_pct)

def compute_ratio_text(score: float) -> str:
    """감성점수 비교 텍스트 생성"""
    if avg_all_score <= 0:
        return ""
    ratio = score / avg_all_score
    if ratio >= 1:
        return f"주변 맛집 평균점수({avg_all_score:.1f})보다 {ratio:.1f}배 더 긍정적이에요!"
    else:
        return f"주변 맛집 평균점수({avg_all_score:.1f})의 {ratio:.1f}배 정도의 긍정도에요."

def get_review_text_from_db(name: str) -> str:
    """레스토랑 이름으로 리뷰 텍스트 조회"""
    if df_reviews.empty:
        return ""
    rest_df = df_reviews[df_reviews["Restaurant_Name"] == name]
    if rest_df.empty:
        return ""
    return " ".join(rest_df["Content"].dropna().tolist())

def split_into_sentences(text: str) -> List[str]:
    """텍스트를 문장으로 분할"""
    text_for_split = re.sub(r"[^\w\s\.\,\?\!\~\ㄱ-ㅎㅏ-ㅣ가-힣]", " ", str(text))
    sents = [s.text.strip() for s in kiwi.split_into_sents(text_for_split) if s.text.strip()]
    unique = []
    for s in sents:
        if s not in unique and len(s) > 1:
            unique.append(s)
    return unique

def categorize_sentences(sentences: List[str]) -> Tuple[List[str], List[str]]:
    """문장들을 긍정/부정으로 분류"""
    pos_list, neg_list, neu_list = [], [], []
    for s in sentences:
        pos_score = sum(1 for kw in POSITIVE_KEYWORDS if kw in s)
        neg_score = sum(1 for kw in NEGATIVE_KEYWORDS if kw in s)
        if pos_score > neg_score:
            pos_list.append(s)
        elif neg_score > pos_score:
            neg_list.append(s)
        else:
            neu_list.append(s)
    
    # 중립 문장 중 음식 관련은 긍정으로 분류
    for s in neu_list:
        if any(k in s for k in ["음식", "가격", "양", "맛", "서비스"]):
            pos_list.append(s)
    
    return pos_list, neg_list

def generate_kobart_summary(text: str, max_length: int = 100) -> str:
    """KoBART를 사용한 텍스트 요약 (지연 로딩 적용)"""
    if not text or not text.strip():
        return "요약할 내용이 없습니다."
    
    # 지연 로딩
    model, tokenizer = load_kobart_model()
    
    inputs = tokenizer(
        text,
        return_tensors="pt",
        truncation=True,
        max_length=512
    )
    inputs = {k: v.to(DEVICE) for k, v in inputs.items()}
    
    with torch.no_grad():
        summary_ids = model.generate(
            inputs["input_ids"],
            attention_mask=inputs["attention_mask"],
            max_length=max_length,
            num_beams=4,
            length_penalty=1.2,
            early_stopping=True,
            no_repeat_ngram_size=2,
            do_sample=False  # 일관성을 위해 샘플링 비활성화
        )
    decoded = tokenizer.decode(summary_ids[0], skip_special_tokens=True)
    sentences = [s.strip() for s in decoded.split(".") if s.strip()]
    formatted = "\n".join(f"- {s}." for s in sentences[:3])
    return formatted if formatted else "요약할 내용이 없습니다."