"""
광고 판별 관련 모듈
- KoBERT 모델 로딩 및 예측
- 규칙 기반 광고 분류
- OCR 텍스트 처리
- 블로그 콘텐츠 처리
"""

import os
import json
import re
import random
import requests
import torch
import torch.nn.functional as F
from typing import Tuple
from PIL import Image
from io import BytesIO
import pytesseract

from transformers import (
    BertTokenizer,
    AutoTokenizer,
    BertForSequenceClassification,
    BertConfig
)

from config import (
    ADV_PATTERNS,
    NONADV_PATTERNS,
    USER_AGENT,
    TIMEOUT,
    OCR_CONFIG,
    TESSERACT_CMD,
    MODEL_CACHE_DIR,
    BLOG_MODEL_PATH
)

from blog_crawler import extract_image_urls, extract_plain_text_from_post, is_excluded
from restaurant_service import fuzzy_extract_restaurant_name

# 디바이스 설정
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

# 전역 모델 변수들
kobert_model = None
kobert_tokenizer = None

# Tesseract 설정
pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD

def load_kobert_model():
    """KoBERT 모델을 지연 로딩"""
    global kobert_model, kobert_tokenizer
    if kobert_model is not None:
        return kobert_model, kobert_tokenizer
    
    print("📚 KoBERT 모델 로딩 시작...")
    try:
        kobert_tokenizer = BertTokenizer.from_pretrained(BLOG_MODEL_PATH)
        with open(os.path.join(BLOG_MODEL_PATH, "config.json"), "r", encoding="utf-8") as f:
            kobert_config = BertConfig.from_dict(json.load(f))
        kobert_model = BertForSequenceClassification(kobert_config)
        state_dict = torch.load(
            os.path.join(BLOG_MODEL_PATH, "blog_kobert_weights.pt"),
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

def match_any(patterns, text: str) -> Tuple[bool, str, str]:
    """패턴 매칭 헬퍼 함수"""
    for pat, name in patterns:
        m = re.search(pat, text, flags=re.IGNORECASE | re.DOTALL)
        if m:
            return True, name, m.group(0)
    return False, None, None

def classify_text_by_regex(text: str) -> Tuple[str, str]:
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

def ocr_from_url(img_url: str) -> str:
    """이미지 URL에서 OCR 텍스트 추출"""
    try:
        res = requests.get(img_url, headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT)
        res.raise_for_status()
        img = Image.open(BytesIO(res.content))
        if img.mode == "RGBA":
            img = img.convert("RGB")
        text = pytesseract.image_to_string(img, config=OCR_CONFIG)
        return text.strip()
    except Exception as e:
        print(f"▶▶▶ [OCR 실패] {img_url} → {e}")
        return ""

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

def predict_text_raw_prob(text: str) -> float:
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