# backend/main.py

import os

# HuggingFace 토크나이저 병렬 처리 경고 제거
os.environ["TOKENIZERS_PARALLELISM"] = "false"
import json
import re
import ast
import requests
import pandas as pd
import torch
import torch.nn.functional as F
import random

from fastapi import FastAPI, HTTPException, Form
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from transformers import (
    BertTokenizer,
    BertForSequenceClassification,
    BertConfig,
    BartForConditionalGeneration,
    PreTrainedTokenizerFast
)
from kiwipiepy import Kiwi
from bs4 import BeautifulSoup
from rapidfuzz import fuzz
import uvicorn
from dotenv import load_dotenv
import asyncio
import aiohttp
from concurrent.futures import ThreadPoolExecutor, as_completed
import functools
import time
from typing import Optional, List, Tuple

# OCR 관련 imports
from urllib.parse import urljoin
from io import BytesIO
from PIL import Image
import pytesseract

from data import restaurant_db, restaurant_aliases
from feedback_system import (
    feedback_manager, 
    create_ad_feedback, 
    create_restaurant_feedback,
    create_search_feedback,
    FeedbackType
)

# ─────────────────────────────────────────────────────────────────────────────
# 0) 환경 변수 로드 및 OCR 설정
# ─────────────────────────────────────────────────────────────────────────────
load_dotenv()  # .env 파일 로드
CLIENT_ID     = os.getenv("NAVER_CLIENT_ID", "").strip()
CLIENT_SECRET = os.getenv("NAVER_CLIENT_SECRET", "").strip()

# Tesseract 설정 (macOS)
pytesseract.pytesseract.tesseract_cmd = "/opt/homebrew/bin/tesseract"
OCR_CONFIG = "--psm 6 --oem 3 -l kor+eng"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
TIMEOUT = 20

# 광고/비광고 판별 정규식 패턴
ADV_PATTERNS = [
    (r'#?\s*협찬', '협찬'),
    (r'유료\s*광고\s*포함', '유료광고 포함'),
    (r'소정의\s*원고료.*(지원|제공).*(작성|후기)', '소정의 원고료 지원/제공'),
    (r'소정의\s*광고료를\s*받고\s*(작성|게시)', '소정의 광고료를 받고 작성'),
    (r'이\s*포스팅은\s*소정의\s*광고료를\s*받고\s*작성했습니다', '이 포스팅은 소정의 광고료를 받고 작성했습니다'),
    (r'업체(?:로부터)?\s*(제공|지원).*(작성|후기)', '업체 제공/지원'),
    (r'업체로', '업체로'),
    (r'지급받', '지급받'),
    (r'제공받', '제공받'),
    (r'지원받', '지원받'),
    (r'서비스를\s*제공받아\s*(작성|리뷰)', '서비스를 제공받아 작성'),
    (r'할인을\s*제공받아\s*(작성|리뷰)', '할인을 제공받아 작성'),
    (r'본\s*포스팅은\s*해당\s*업체로부터\s*서비스를\s*제공받아\s*작성된\s*리뷰', '본 포스팅은 해당업체로부터 서비스를 제공받아 작성된 리뷰'),
    (r'이\s*글은.*앱을\s*통해\s*할인을\s*제공받아\s*작성', '앱을 통해 할인을 제공받아 작성'),
    # 체험단/서포터즈 관련
    (r'(체험단|서포터즈|리뷰어|블로거)\s*(선정|모집|활동)', '체험단/서포터즈 활동'),
    (r'슈퍼멤버스', '슈퍼멤버스'),
    (r'super\s*members?', '슈퍼멤버스(영문)'),
    (r'무료\s*(체험|이용|제공).*(후기|리뷰)', '무료 체험 후기'),
    (r'(무료|공짜)로\s*(받아서|이용해서|체험해서)', '무료 제공 받음'),
    # 업체 직접 연락/섭외
    (r'업체.*연락.*받아', '업체 연락 받음'),
    (r'(섭외|요청).*받아서', '섭외/요청 받음'),
    # 광고임을 나타내는 일반적 표현
    (r'(광고|AD|advertisement).*포함', '광고 포함 표시'),
    (r'(유료|페이드|paid).*포스팅', '유료 포스팅'),
    (r'(제휴|파트너십|partnership)', '제휴/파트너십'),
    (r'(유료|포함|협찬|제공|지원).{0,8}광고|광고.{0,8}(유료|포함|협찬|제공|지원)', '광고(보조키워드 포함)'),
]

NONADV_PATTERNS = [
    (r'100%\s*내돈내산', '100% 내돈내산'),
    (r'내돈내산', '내돈내산'),
    # 직접 구매/결제 관련
    (r'(직접|개인적으로)\s*(구매|결제|주문)', '직접 구매/결제'),
    (r'(내\s*돈|제\s*돈|개인\s*돈).*주고', '개인 돈으로 구매'),
    (r'(카드|현금|계좌이체)로\s*(결제|지불)', '직접 결제'),
    (r'(가격|금액|비용).*지불하고', '비용 지불'),
    # 개인적 경험 강조
    (r'(개인적인|주관적인|솔직한)\s*(의견|생각|후기)', '개인적 의견'),
    (r'(진짜|정말|솔직히)\s*(후기|리뷰)', '솔직한 후기'),
    (r'(실제|진짜)\s*(먹어보고|가봤는데|이용해보고)', '실제 경험'),
    # 단점/부정적 측면 언급
    (r'(단점|아쉬운\s*점|문제점)', '단점 언급'),
    (r'(별로|실망|아쉽)', '부정적 평가'),
    (r'(비추|추천\s*안함|권하지\s*않)', '비추천'),
    # 솔직함 강조
    (r'(솔직|정직)한\s*(후기|리뷰|평가)', '솔직한 후기'),
    (r'(가감없이|있는\s*그대로|진실한)', '가감없는 후기'),
    (r'(편견없이|객관적으로)', '객관적 후기'),
    # 개인 취향/의견 표현
    (r'(개인\s*취향|제\s*취향|개인차)', '개인 취향'),
    (r'(주관적|개인적)\s*(생각|의견)', '주관적 의견'),
    # 실제 방문 확인
    (r'(실제로|정말로)\s*(가봤|먹어봤|이용해봤)', '실제 방문'),
    (r'(몇\s*번|여러\s*번)\s*(가봤|방문)', '여러 번 방문'),
]

# ─────────────────────────────────────────────────────────────────────────────
# 1) FastAPI & CORS 설정
# ─────────────────────────────────────────────────────────────────────────────
app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─────────────────────────────────────────────────────────────────────────────
# 2) 디바이스 및 모델 로드 (최적화된 버전)
# ─────────────────────────────────────────────────────────────────────────────
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
print(f"🔧 사용 디바이스: {DEVICE}")

# 전역 모델 변수들
kobert_model = None
kobert_tokenizer = None
kobart_model = None  
kobart_tokenizer = None

def load_kobert_model():
    """KoBERT 모델을 지연 로딩"""
    global kobert_model, kobert_tokenizer
    if kobert_model is not None:
        return kobert_model, kobert_tokenizer
    
    print("📚 KoBERT 모델 로딩 시작...")
    kobert_model_path = os.path.join(os.path.dirname(__file__), "blog_model")
    try:
        kobert_tokenizer = BertTokenizer.from_pretrained(kobert_model_path)
        with open(os.path.join(kobert_model_path, "config.json"), "r", encoding="utf-8") as f:
            kobert_config = BertConfig.from_dict(json.load(f))
        kobert_model = BertForSequenceClassification(kobert_config)
        state_dict = torch.load(
            os.path.join(kobert_model_path, "blog_kobert_weights.pt"),
            map_location=DEVICE,
            weights_only=True  # 보안 강화
        )
        kobert_model.load_state_dict(state_dict)
        kobert_model.to(DEVICE)
        kobert_model.eval()
        
        # 메모리 최적화
        if hasattr(torch.backends, 'cudnn'):
            torch.backends.cudnn.benchmark = True
            
        print("✅ KoBERT 광고 판별 모델 로드 완료")
        return kobert_model, kobert_tokenizer
    except Exception as e:
        raise RuntimeError(f"KoBERT 모델 로드 중 오류 발생: {e}")

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
            cache_dir=MODEL_CACHE_DIR,  # 로컬 캐시 디렉토리 설정
            torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32  # 혼합 정밀도
        )
        kobart_model.to(DEVICE)
        kobart_model.eval()
        
        # 메모리 최적화
        if hasattr(torch.backends, 'cudnn'):
            torch.backends.cudnn.benchmark = True
            
        print("✅ KoBART 리뷰 요약 모델 로드 완료")
        return kobart_model, kobart_tokenizer
    except Exception as e:
        raise RuntimeError(f"KoBART 모델 로드 중 오류 발생: {e}")

# 서버 시작시에는 모델 로딩하지 않음 (지연 로딩)

# 모델 캐시 디렉토리 생성
MODEL_CACHE_DIR = os.path.join(os.path.dirname(__file__), "model_cache")
os.makedirs(MODEL_CACHE_DIR, exist_ok=True)

# ThreadPoolExecutor for CPU-intensive tasks
executor = ThreadPoolExecutor(max_workers=4)

# 블로그 크롤링 결과 캐시 (메모리 캐시)
blog_cache = {}
CACHE_EXPIRY = 300  # 5분

# ─────────────────────────────────────────────────────────────────────────────
# 최적화된 비동기 크롤링 함수들
# ─────────────────────────────────────────────────────────────────────────────

def get_cache_key(url: str) -> str:
    """캐시 키 생성"""
    return f"blog_{hash(url)}"

def is_cache_valid(timestamp: float) -> bool:
    """캐시 유효성 검사"""
    return time.time() - timestamp < CACHE_EXPIRY

async def fetch_post_html_async(session: aiohttp.ClientSession, blog_url: str) -> str:
    """비동기 HTML 페치 (캐시 적용)"""
    cache_key = get_cache_key(blog_url)
    
    # 캐시 확인
    if cache_key in blog_cache:
        cached_data, timestamp = blog_cache[cache_key]
        if is_cache_valid(timestamp):
            return cached_data
    
    try:
        headers = {"User-Agent": UA}
        async with session.get(blog_url, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as response:
            if response.status != 200:
                return ""
            
            html_content = await response.text()
            soup = BeautifulSoup(html_content, "html.parser")
            iframe = soup.find("iframe", id="mainFrame")
            
            if not iframe or not iframe.get("src"):
                return ""
            
            post_url = urljoin(blog_url, iframe["src"])
            async with session.get(post_url, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as post_response:
                if post_response.status == 200:
                    result = await post_response.text()
                    # 캐시 저장
                    blog_cache[cache_key] = (result, time.time())
                    return result
                return ""
    except Exception as e:
        print(f"▶▶▶ [비동기 HTML 페치 실패] {blog_url} → {e}")
        return ""

def process_blog_content_sync(title: str, link: str, html: str) -> dict:
    """동기 블로그 콘텐츠 처리 (CPU 집약적 작업)"""
    try:
        # HTML 본문 추출
        body_text = extract_plain_text_from_post(html) if html else ""
        
        # OCR은 너무 느리므로 선택적으로만 수행 (규칙 기반으로 광고 의심시에만)
        ocr_text = ""
        body_label, _ = classify_text_by_regex(body_text)
        
        # 본문에서 광고가 확실하지 않을 때만 OCR 수행
        if body_label == "불명" and html:
            ocr_text = get_blog_ocr_text_limited(link, html, max_images=3)  # 이미지 수 제한
        
        ocr_label, _ = classify_text_by_regex(ocr_text)
        final_label = decide_final_label(body_label, ocr_label)
        
        # 모델 원확률 (규칙으로 확실한 경우 모델 건너뛰기)
        if final_label in ["광고", "비광고"]:
            raw_prob = 0.5  # 기본값
        else:
            raw_prob = predict_text_raw_prob(body_text[:512])  # 텍스트 길이 제한
        
        # 표시 확률
        if final_label == "광고":
            shown_prob = random.uniform(70.0, 90.0)
        elif final_label == "비광고":
            shown_prob = random.uniform(15.0, 30.0)
        else:
            shown_prob = min(raw_prob * 100 + random.uniform(10.0, 20.0), 90.0)
        
        # 레스토랑 추출 (제한된 텍스트로)
        restaurant = fuzzy_extract_restaurant_name(title, body_text[:1000]) or "알 수 없음"
        
        return {
            "title": title,
            "link": link,
            "ad_probability": round(shown_prob, 2),
            "restaurant": restaurant,
            "final_label": final_label,
            "body_label": body_label,
            "ocr_label": ocr_label
        }
    except Exception as e:
        print(f"▶▶▶ [콘텐츠 처리 실패] {link} → {e}")
        return {
            "title": title,
            "link": link,
            "ad_probability": 50.0,
            "restaurant": "알 수 없음",
            "final_label": "불명",
            "body_label": "불명",
            "ocr_label": "불명"
        }

def get_blog_ocr_text_limited(link: str, html: str, max_images: int = 3) -> str:
    """제한된 OCR 텍스트 추출 (이미지 수 제한)"""
    try:
        img_urls = [u for u in extract_image_urls(html, link) if not is_excluded(u)][:max_images]
        texts = []
        for u in img_urls:
            t = ocr_from_url(u)
            if t:
                texts.append(t)
        return "\n".join(texts)
    except Exception:
        return ""

# ─────────────────────────────────────────────────────────────────────────────
# OCR 및 광고 판별 헬퍼 함수들
# ─────────────────────────────────────────────────────────────────────────────

def match_any(patterns, text: str):
    for pat, name in patterns:
        m = re.search(pat, text, flags=re.IGNORECASE | re.DOTALL)
        if m:
            return True, name, m.group(0)
    return False, None, None

def classify_text_by_regex(text: str):
    """텍스트(HTML 본문 또는 OCR 텍스트)에 규칙 적용 -> (label, reason)"""
    if not text or not text.strip():
        return "불명", ""
    adv_hit, adv_name, _ = match_any(ADV_PATTERNS, text)
    if adv_hit:
        return "광고", adv_name
    nonadv_hit, nonadv_name, _ = match_any(NONADV_PATTERNS, text)
    if nonadv_hit:
        return "비광고", nonadv_name
    return "불명", ""

def decide_final_label(body_label: str, ocr_label: str) -> str:
    """본문/OCR 충돌 시 비광고 우선."""
    if body_label == "비광고" or ocr_label == "비광고":
        return "비광고"
    if body_label == "광고" or ocr_label == "광고":
        return "광고"
    return "비광고"  # 둘 다 불명 → 비광고(추정)

def fetch_post_html(blog_url: str) -> str:
    """네이버 블로그 iframe 진입"""
    headers = {"User-Agent": UA}
    try:
        r = requests.get(blog_url, headers=headers, timeout=TIMEOUT)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        iframe = soup.find("iframe", id="mainFrame")
        if not iframe or not iframe.get("src"):
            return ""
        post_url = urljoin(blog_url, iframe["src"])
        r2 = requests.get(post_url, headers=headers, timeout=TIMEOUT)
        r2.raise_for_status()
        return r2.text
    except Exception as e:
        print(f"▶▶▶ [HTML 페치 실패] {blog_url} → {e}")
        return ""

def extract_plain_text_from_post(html: str) -> str:
    """HTML 본문 전체 텍스트 추출"""
    soup = BeautifulSoup(html, "html.parser")
    return soup.get_text(separator="\n", strip=True)

def extract_image_urls(html: str, base_url: str):
    soup = BeautifulSoup(html, "html.parser")
    urls = []
    for comp in soup.find_all("div", class_=lambda c: c and "se-module" in c and "video" not in c):
        for img in comp.find_all("img"):
            url = img.get("data-lazy-src") or img.get("src")
            if url:
                urls.append(urljoin(base_url, url))
    return urls

def is_excluded(url: str) -> bool:
    return ("postfiles.pstatic.net" in url and "?type=" in url)

def ocr_from_url(img_url: str) -> str:
    try:
        res = requests.get(img_url, headers={"User-Agent": UA}, timeout=TIMEOUT)
        res.raise_for_status()
        img = Image.open(BytesIO(res.content))
        if img.mode == "RGBA":
            bg = Image.new("RGBA", img.size, (255, 255, 255, 255))
            img = Image.alpha_composite(bg, img).convert("RGB")
        text = pytesseract.image_to_string(img, config=OCR_CONFIG).strip()
        return text
    except Exception as e:
        print(f"▶▶▶ [OCR 실패] {img_url} → {e}")
        return ""

def get_blog_ocr_text(link: str, max_images: int = 15) -> str:
    """이미지 OCR 텍스트 합치기"""
    html = fetch_post_html(link)
    if not html:
        return ""
    img_urls = [u for u in extract_image_urls(html, link) if not is_excluded(u)]
    texts = []
    for u in img_urls[:max_images]:
        t = ocr_from_url(u)
        if t:
            texts.append(t)
    return "\n".join(texts)

def predict_text_raw_prob(text):
    """KoBERT 원확률(0~1)"""
    if not text or not text.strip():
        return 0.0
    
    # 지연 로딩
    model, tokenizer = load_kobert_model()
    
    inputs = tokenizer(
        text,
        return_tensors="pt",
        truncation=True,
        padding="max_length",
        max_length=512
    ).to(DEVICE)
    with torch.no_grad():
        outputs = model(**inputs)
        probs = F.softmax(outputs.logits, dim=1)
        return float(probs[0][1].item())

def predict_ad_probability(text: str) -> float:
    """새로운 광고 판별 함수: 규칙 기반 + OCR + 모델"""
    if not text:
        return 0.0
    
    # 규칙 기반 분류
    text_label, _ = classify_text_by_regex(text)
    
    # 모델 원확률
    raw_prob = predict_text_raw_prob(text)
    
    # 최종 확률 계산
    if text_label == "광고":
        return random.uniform(0.70, 0.90)  # 70-90%
    elif text_label == "비광고":
        return random.uniform(0.15, 0.30)  # 15-30%
    else:
        # 불명인 경우 모델 확률 사용하되 보정
        return min(raw_prob + random.uniform(0.1, 0.2), 0.9)

# KoBART 모델은 지연 로딩으로 처리됨 (load_kobart_model 함수 참조)

# 2-3) Kiwi tokenizer
kiwi = Kiwi()

# ─────────────────────────────────────────────────────────────────────────────
# 3) 감성 키워드 사전
# ─────────────────────────────────────────────────────────────────────────────
POSITIVE_KEYWORDS = [
    "맛있", "좋", "훌륭", "친절", "쾌적", "넓", "깔끔", "신선",
    "추천", "최고", "만족", "즐겁", "행복", "재방문", "감동",
    "기대 이상", "든든", "잘먹", "깨끗", "편안", "굿", "가성비",
    "배부르", "합리적", "따뜻", "기대", "존맛", "강추", "푸짐"
]
NEGATIVE_KEYWORDS = [
    "별로", "나쁘", "아쉽", "부족", "좁", "불편", "비싸", "문제",
    "실망", "최악", "짜증", "이상", "불친절", "더러움", "없어",
    "불쾌", "냄새", "기대 이하", "맛없", "질감", "차가워", "불만",
    "짜다", "늦게", "식어", "질기다", "평범", "웨이팅", "기다리게", "아깝다",
    "소음", "시끄럽", "오래", "불결", "복잡"
]

# ─────────────────────────────────────────────────────────────────────────────
# 4) 해시태그 + 감성점수 CSV 로드
# ─────────────────────────────────────────────────────────────────────────────
this_dir = os.path.dirname(__file__)
sentiment_csv_path = os.path.join(this_dir, "store_sentiment_result.csv")
if not os.path.isfile(sentiment_csv_path):
    raise FileNotFoundError(f"'{sentiment_csv_path}' 파일이 없습니다.")

hashtag_df = pd.read_csv(sentiment_csv_path)
all_scores = hashtag_df["감성점수"].astype(float)
avg_all_score = float(all_scores.mean())

def get_hashtags_and_score(name: str):
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
    rank_pct = (all_scores <= score).sum() / len(all_scores) * 100
    return float(rank_pct)

def compute_ratio_text(score: float) -> str:
    if avg_all_score <= 0:
        return ""
    ratio = score / avg_all_score
    if ratio >= 1:
        return f"주변 맛집 평균점수({avg_all_score:.1f})보다 {ratio:.1f}배 더 긍정적이에요!"
    else:
        return f"주변 맛집 평균점수({avg_all_score:.1f})의 {ratio:.1f}배 정도의 긍정도에요."

# ─────────────────────────────────────────────────────────────────────────────
# 5) 리뷰 CSV 로드
# ─────────────────────────────────────────────────────────────────────────────
csv_path = os.path.join(this_dir, "processed_reviews.csv")
if not os.path.isfile(csv_path):
    raise FileNotFoundError(f"'{csv_path}' 파일이 없습니다.")
df_reviews = pd.read_csv(csv_path)

def get_review_text_from_db(name: str) -> str:
    rest_df = df_reviews[df_reviews["Restaurant_Name"] == name]
    if rest_df.empty:
        return ""
    return " ".join(rest_df["Content"].dropna().tolist())

# ─────────────────────────────────────────────────────────────────────────────
# 6) 네이버 블로그 검색 & 크롤링 (동기 함수)
# ─────────────────────────────────────────────────────────────────────────────

CLIENT_ID = "gth14BiagKH3bYs4Nfut"
CLIENT_SECRET = "Dd6SRXZecD"

def naver_blog_search(query: str, search_strategy: str = "sim_random"):
    """
    관련도 순 기반 블로그 검색 (매번 다른 결과)
    
    Args:
        query: 검색어
        search_strategy: 검색 전략 (기본값: sim_random)
            - "sim_random": 관련도 순으로 더 많이 가져와서 랜덤 선택 (기본값)
    """
    url = "https://openapi.naver.com/v1/search/blog.json"
    headers = {
        "X-Naver-Client-Id": CLIENT_ID,
        "X-Naver-Client-Secret": CLIENT_SECRET
    }
    
    all_results = []
    
    try:
        if search_strategy == "sim_random":
            # 관련도 순 기반으로 더 많이 가져와서 랜덤 선택
            import random
            import hashlib
            import time
            
            print(f"🔍 [관련도 순 + 랜덤 선택] {query}")
            
            # 시간 기반 시드로 매번 다른 결과 보장
            time_seed = int(time.time() * 1000) % 10000  # 밀리초 단위
            query_hash = int(hashlib.md5(query.encode()).hexdigest()[:8], 16) % 1000
            seed = (time_seed + query_hash) % 10000
            random.seed(seed)
            
            # 관련도 순으로 더 많이 가져오기 (50개)
            params = {"query": query, "display": 50, "sort": "sim"}
            response = requests.get(url, headers=headers, params=params, timeout=5)
            
            if response.status_code == 200:
                result = response.json()
                items = result.get("items", [])
                all_candidates = [(item["title"], item["link"]) for item in items]
                
                # 중복 제거
                seen_links = set()
                unique_results = []
                for title, link in all_candidates:
                    if link not in seen_links:
                        unique_results.append((title, link))
                        seen_links.add(link)
                
                # 랜덤 셔플 후 18개 선택 (관련도 높은 것들 중에서)
                random.shuffle(unique_results)
                all_results = unique_results[:18]
                
                print(f"✅ 관련도 순 {len(all_candidates)}개 중 {len(all_results)}개 선택 (시드: {seed})")
            else:
                print(f"▶▶▶ [네이버 API 에러] status_code={response.status_code}")
                return []
            
        elif search_strategy == "mixed":
            # 전략 1: 관련도순 10개 + 최신순 8개로 다양성 확보 (총 18개 목표)
            print(f"🔍 [혼합 검색] {query}")
            
            # 관련도순 10개
            params_sim = {"query": query, "display": 10, "sort": "sim"}
            response_sim = requests.get(url, headers=headers, params=params_sim, timeout=5)
            if response_sim.status_code == 200:
                result_sim = response_sim.json()
                sim_items = result_sim.get("items", [])
                all_results.extend([(item["title"], item["link"]) for item in sim_items])
                print(f"✅ 관련도순: {len(sim_items)}개")
            
            # 최신순 12개 (중복 제거 후 8개 정도 남을 예상)
            params_date = {"query": query, "display": 12, "sort": "date"}
            response_date = requests.get(url, headers=headers, params=params_date, timeout=5)
            if response_date.status_code == 200:
                result_date = response_date.json()
                date_items = result_date.get("items", [])
                
                # 중복 제거 (링크 기준)
                existing_links = {link for _, link in all_results}
                unique_date_items = [
                    (item["title"], item["link"]) 
                    for item in date_items 
                    if item["link"] not in existing_links
                ]
                all_results.extend(unique_date_items[:8])  # 최대 8개만
                print(f"✅ 최신순 (중복제거): {len(unique_date_items[:8])}개")
                
        elif search_strategy == "random":
            # 전략 2: 많은 후보에서 랜덤하게 18개 선택
            print(f"🎲 [랜덤 검색] {query}")
            
            # 관련도순 15개 + 최신순 15개 = 총 30개 후보
            for sort_type in ["sim", "date"]:
                params = {"query": query, "display": 15, "sort": sort_type}
                response = requests.get(url, headers=headers, params=params, timeout=5)
                if response.status_code == 200:
                    result = response.json()
                    items = result.get("items", [])
                    all_results.extend([(item["title"], item["link"]) for item in items])
            
            # 중복 제거
            seen_links = set()
            unique_results = []
            for title, link in all_results:
                if link not in seen_links:
                    unique_results.append((title, link))
                    seen_links.add(link)
            
            # 랜덤하게 18개 선택
            if len(unique_results) > 18:
                import random
                all_results = random.sample(unique_results, 18)
            else:
                all_results = unique_results
                
            print(f"✅ 랜덤 선택: {len(all_results)}개")
            
        else:
            # 전략 3: 단일 정렬 방식 (sim 또는 date)
            print(f"📋 [단일 검색] {query} - {search_strategy}")
            params = {"query": query, "display": 18, "sort": search_strategy}
            response = requests.get(url, headers=headers, params=params, timeout=5)
            
            if response.status_code != 200:
                print(f"▶▶▶ [네이버 API 에러] status_code={response.status_code}")
                return []
                
            result = response.json()
            items = result.get("items", [])
            all_results = [(item["title"], item["link"]) for item in items]
            print(f"✅ {search_strategy}순: {len(all_results)}개")
        
        print(f"🎯 최종 결과: {len(all_results)}개 블로그")
        return all_results[:18]  # 최대 18개 반환
        
    except Exception as e:
        print(f"▶▶▶ [네이버 검색 예외] {e}")
        return []

def crawl_blog_text(link: str) -> str:
    """기존 호환성을 위한 간단한 크롤링 함수"""
    html = fetch_post_html(link)
    return extract_plain_text_from_post(html) if html else ""

def clean_text(text: str) -> str:
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"[\"'‘’“”()\[\]{}]", "", text)
    text = re.sub(r"[^가-힣a-zA-Z0-9\s]", " ", text)
    return text.strip()

def fuzzy_extract_restaurant_name(title: str, text: str) -> str:
    full_raw = clean_text(title + " " + text)
    full = full_raw.replace(" ", "")
    best_name, best_score = None, 0
    for name, aliases in restaurant_aliases.items():
        candidates = [name] + aliases
        for alias in candidates:
            alias_nospace = alias.replace(" ", "")
            score_val = fuzz.partial_ratio(alias_nospace, full)
            if score_val > best_score and score_val >= 60:
                best_score = score_val
                best_name = name
    return best_name

# ─────────────────────────────────────────────────────────────────────────────
# 7) KoBART 리뷰 요약·감성 분석 헬퍼
# ─────────────────────────────────────────────────────────────────────────────
def split_into_sentences(text: str) -> list:
    text_for_split = re.sub(r"[^\w\s\.\,\?\!\~\ㄱ-ㅎㅏ-ㅣ가-힣]", " ", str(text))
    sents = [s.text.strip() for s in kiwi.split_into_sents(text_for_split) if s.text.strip()]
    unique = []
    for s in sents:
        if s not in unique and len(s) > 1:
            unique.append(s)
    return unique

def categorize_sentences(sentences: list) -> tuple:
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

# ─────────────────────────────────────────────────────────────────────────────
# 7) 헬스체크 및 모델 워밍업 엔드포인트
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
# 8) /api/restaurant/{name} 엔드포인트
# ─────────────────────────────────────────────────────────────────────────────
@app.get("/api/restaurant/{name}", response_class=JSONResponse)
async def restaurant_detail(name: str):
    print(f"🍽️ [상세정보 요청] {name}")
    start_time = time.time()
    
    info = restaurant_db.get(name)
    if not info:
        raise HTTPException(status_code=404, detail=f"'{name}'에 대한 정보가 없습니다.")

    print(f"📊 [1단계] 기본 정보 로드 완료 ({time.time() - start_time:.2f}초)")
    
    # 1단계: 해시태그와 감성점수 (빠른 처리)
    pos_tags_all, neg_tags_all, score = get_hashtags_and_score(name)
    sentiment_percentile = compute_percentile(score)
    sentiment_ratio = compute_ratio_text(score)
    print(f"📈 [2단계] 감성분석 완료 ({time.time() - start_time:.2f}초)")

    # 2단계: 리뷰 텍스트 처리 (중간 처리)
    review_content = get_review_text_from_db(name)
    sentences = split_into_sentences(review_content)
    pos_sents, neg_sents = categorize_sentences(sentences)
    print(f"📝 [3단계] 리뷰 분석 완료 ({time.time() - start_time:.2f}초)")
    
    # 3단계: KoBART 요약 생성 (시간 소요)
    pos_text = " ".join(pos_sents)
    neg_text = " ".join(neg_sents)
    
    print(f"🤖 [4단계] AI 요약 생성 시작...")
    summary_result = {
        "positive": generate_kobart_summary(pos_text, max_length=80) \
            if pos_sents else "- 긍정적인 평가가 없습니다.",
        "negative": generate_kobart_summary(neg_text, max_length=80) \
            if neg_sents else "- 부정적인 평가가 없습니다.",
        "overall": generate_kobart_summary(review_content, max_length=120)
    }
    print(f"✅ [5단계] AI 요약 완료 ({time.time() - start_time:.2f}초)")

    # 4단계: 블로그 검색 및 광고 확률 (옵션, 빠르게 처리)
    try:
        blogs = naver_blog_search(name)
        combined_texts = []
        # 최대 3개의 블로그만 검색해서 성능 개선
        for title, link in blogs[:3]:
            txt = crawl_blog_text(link)
            if txt:
                combined_texts.append(txt)
        combined_all = " ".join(combined_texts)
        ad_prob = round(predict_ad_probability(combined_all) * 100, 2) if combined_all else 0.0
        print(f"🔍 [6단계] 블로그 분석 완료 ({time.time() - start_time:.2f}초)")
    except Exception as e:
        print(f"⚠️ [6단계] 블로그 분석 실패: {e}")
        ad_prob = 0.0

    total_time = time.time() - start_time
    print(f"🎉 [완료] {name} 상세정보 처리 완료 (총 {total_time:.2f}초)")

    return JSONResponse(
        status_code=200,
        content={
            "status": "ok",
            "data": {
                "name": name,
                "category": info.get("category"),
                "naver_place": info.get("naver_place"),
                "review_url": info.get("review_url"),
                "address": info.get("address"),
                "map_embed": info.get("kakao_map_embed"),
                "hashtags": {
                    "positive": pos_tags_all,
                    "negative": neg_tags_all
                },
                "sentiment_score": score,
                "sentiment_percentile": round(sentiment_percentile, 1),
                "sentiment_ratio_text": sentiment_ratio,
                "blog_ad_probability": ad_prob,
                "kobart_summary": summary_result
            }
        }
    )

# ─────────────────────────────────────────────────────────────────────────────
# 9) /api/crawl_predict 엔드포인트 (최적화된 버전)
# ─────────────────────────────────────────────────────────────────────────────
@app.post("/api/crawl_predict", response_class=JSONResponse)
async def crawl_predict_json(
    query: str = Form(...)
):
    """최적화된 블로그 광고 판별 API - 병렬 처리 및 캐싱 적용
    
    Args:
        query: 검색어
    """
    if not query or not query.strip():
        raise HTTPException(status_code=400, detail="query가 비어 있습니다.")

    print(f"🔍 검색 시작: {query}")
    start_time = time.time()
    
    # 네이버 블로그 검색 (관련도 순 기반 + 랜덤 선택)
    search_results = naver_blog_search(query, "sim_random")
    if not search_results:
        return JSONResponse(status_code=200, content={"status": "ok", "data": []})
    
    print(f"📝 {len(search_results)}개 블로그 찾음")
    
    # 비동기로 HTML 페치
    async with aiohttp.ClientSession() as session:
        html_tasks = []
        for title, link in search_results:
            task = fetch_post_html_async(session, link)
            html_tasks.append((title, link, task))
        
        # HTML 페치 완료 대기
        blog_data = []
        for title, link, task in html_tasks:
            try:
                html = await task
                blog_data.append((title, link, html))
            except Exception as e:
                print(f"▶▶▶ [HTML 페치 실패] {link} → {e}")
                blog_data.append((title, link, ""))
    
    print(f"🌐 HTML 페치 완료: {time.time() - start_time:.2f}초")
    
    # CPU 집약적 작업을 병렬로 처리
    futures = []
    for title, link, html in blog_data:
        future = executor.submit(process_blog_content_sync, title, link, html)
        futures.append(future)
    
    # 결과 수집
    final = []
    for future in as_completed(futures):
        try:
            result = future.result(timeout=30)  # 30초 타임아웃
            final.append(result)
        except Exception as e:
            print(f"▶▶▶ [콘텐츠 처리 실패] → {e}")
            continue
    
    # 블로그별 평균 평점과 추천 횟수 가져오기
    blog_rating_stats = feedback_manager.get_blog_average_ratings()
    print(f"🔍 [디버깅] 전체 블로그 평점 통계: {blog_rating_stats}")
    
    # 각 결과에 평점 정보 추가
    for result in final:
        blog_url = result.get("link", "")
        blog_stats = blog_rating_stats.get(blog_url, {})
        
        result["recommendation_count"] = blog_stats.get("recommendation_count", 0)
        result["average_rating"] = blog_stats.get("average_rating", 0)
        result["total_ratings"] = blog_stats.get("total_ratings", 0)
        
        if blog_stats:
            print(f"🔍 [블로그 확인] {blog_url} → {blog_stats['recommendation_count']}회 추천, 평균 {blog_stats['average_rating']}점 ({blog_stats['total_ratings']}개 평가)")
        if blog_stats.get("recommendation_count", 0) > 0:
            print(f"✅ [추천 블로그 발견] {blog_url} → {blog_stats['recommendation_count']}회 추천, 평균 {blog_stats['average_rating']}점")
    
    # 블로그 기반 추천 정렬 로직
    # 시간 기반 시드로 매번 다른 결과
    time_seed = int(time.time() * 1000) % 10000
    random.seed(time_seed)
    
    # 1. 추천받은 블로그와 일반 블로그 분리
    recommended_blogs = []
    other_blogs = []
    
    for result in final:
        recommendation_count = result.get("recommendation_count", 0)
        if recommendation_count > 0:
            recommended_blogs.append(result)
        else:
            other_blogs.append(result)
    
    # 2. 추천받은 블로그들을 추천 횟수 순으로 정렬
    recommended_blogs.sort(key=lambda x: (-x["recommendation_count"], -x["average_rating"], x["ad_probability"]))
    print(f"🔍 [추천 블로그 수] 총 {len(recommended_blogs)}개 추천 블로그 발견")
    
    # 상위 3개 추천 블로그 (있는 만큼만)
    top_recommended = recommended_blogs[:3]
    print(f"🏆 [상위 추천] {len(top_recommended)}개 블로그를 상위에 배치")
    for i, blog in enumerate(top_recommended):
        print(f"   {i+1}위: {blog['recommendation_count']}회 추천({blog['average_rating']}점) - {blog.get('title', '')[:30]}...")
    
    # 나머지 추천 블로그들은 other_blogs에 추가
    other_recommended = recommended_blogs[3:]
    other_blogs.extend(other_recommended)
    
    # 3. 나머지 블로그들은 랜덤 셔플 (관련도 기반이지만 매번 다르게)
    random.shuffle(other_blogs)
    
    # 4. 최종 결과: 상위 추천 블로그 + 나머지 랜덤
    final = top_recommended + other_blogs
    print(f"📊 [최종 배치] 상위 {len(top_recommended)}개 추천 + 나머지 {len(other_blogs)}개 = 총 {len(final)}개")
    
    total_time = time.time() - start_time
    print(f"✅ 전체 처리 완료: {total_time:.2f}초 ({len(final)}개 결과)")
    print(f"📊 상위 {len(top_recommended)}개 추천 블로그 우선 노출, 나머지 {len(other_blogs)}개 랜덤 정렬 (시드: {time_seed})")
    
    return JSONResponse(status_code=200, content={"status": "ok", "data": final})

# 캐시 정리 함수 (백그라운드에서 주기적 실행)
def cleanup_cache():
    """만료된 캐시 항목 정리"""
    current_time = time.time()
    expired_keys = [
        key for key, (_, timestamp) in blog_cache.items() 
        if current_time - timestamp > CACHE_EXPIRY
    ]
    for key in expired_keys:
        del blog_cache[key]
    
    if expired_keys:
        print(f"🧹 캐시 정리 완료: {len(expired_keys)}개 항목 제거")

# 캐시 상태 확인 엔드포인트
@app.get("/api/cache_info")
async def cache_info():
    """캐시 상태 정보 반환"""
    cleanup_cache()  # 정리 후 정보 반환
    return {
        "cache_size": len(blog_cache),
        "cache_expiry_seconds": CACHE_EXPIRY
    }

# ─────────────────────────────────────────────────────────────────────────────
# 사용자 피드백 시스템 API
# ─────────────────────────────────────────────────────────────────────────────
@app.post("/api/feedback/ad-classification")
async def submit_ad_classification_feedback(
    blog_url: str = Form(...),
    blog_title: str = Form(...),
    predicted_probability: float = Form(...),
    is_correct: bool = Form(...),
    comment: str = Form("")
):
    """광고 판별 결과에 대한 사용자 피드백"""
    success = create_ad_feedback(
        blog_url=blog_url,
        blog_title=blog_title,
        predicted_probability=predicted_probability,
        user_says_correct=is_correct,
        user_comment=comment
    )
    
    if success:
        return {"status": "success", "message": "피드백이 저장되었습니다."}
    else:
        raise HTTPException(status_code=500, detail="피드백 저장 중 오류가 발생했습니다.")

@app.post("/api/feedback/restaurant-rating")
async def submit_restaurant_rating_feedback(
    restaurant_name: str = Form(...),
    rating: int = Form(...),
    visited: bool = Form(...),
    blog_url: str = Form(""),
    comment: str = Form("")
):
    """맛집 평가 피드백"""
    print(f"🍽️ [맛집 평가 접수] {restaurant_name} - {rating}점")
    print(f"   📍 blog_url: '{blog_url}'")
    print(f"   🚶 visited: {visited}")
    print(f"   💬 comment: '{comment}'")
    
    if not 1 <= rating <= 5:
        raise HTTPException(status_code=400, detail="평점은 1-5점 사이여야 합니다.")
    
    success = create_restaurant_feedback(
        restaurant_name=restaurant_name,
        rating=rating,
        visited=visited,
        blog_url=blog_url,
        comment=comment
    )
    
    if success:
        print(f"✅ [평가 저장 성공] {restaurant_name} - {rating}점 (blog_url: '{blog_url}')")
        return {"status": "success", "message": "맛집 평가가 저장되었습니다."}
    else:
        print(f"❌ [평가 저장 실패] {restaurant_name}")
        raise HTTPException(status_code=500, detail="평가 저장 중 오류가 발생했습니다.")

@app.post("/api/feedback/search-satisfaction")
async def submit_search_satisfaction_feedback(
    query: str = Form(...),
    satisfaction: int = Form(...),
    found_useful: bool = Form(...)
):
    """검색 만족도 피드백"""
    if not 1 <= satisfaction <= 5:
        raise HTTPException(status_code=400, detail="만족도는 1-5점 사이여야 합니다.")
    
    success = create_search_feedback(
        query=query,
        satisfaction=satisfaction,
        found_useful=found_useful
    )
    
    if success:
        return {"status": "success", "message": "검색 만족도가 저장되었습니다."}
    else:
        raise HTTPException(status_code=500, detail="만족도 저장 중 오류가 발생했습니다.")

@app.get("/api/feedback/stats")
async def get_feedback_stats():
    """피드백 통계 조회"""
    stats = feedback_manager.get_feedback_stats()
    trends = feedback_manager.analyze_feedback_trends()
    
    return {
        "status": "success",
        "data": {
            "basic_stats": stats,
            "trends": trends
        }
    }

@app.get("/api/feedback/detailed-analytics")
async def get_detailed_analytics():
    """상세 피드백 분석 데이터"""
    try:
        analytics = feedback_manager.get_detailed_analytics()
        return {
            "status": "success",
            "data": analytics
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"분석 데이터 조회 실패: {str(e)}")

# ─────────────────────────────────────────────────────────────────────────────
# 10) 앱 실행
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8013)
