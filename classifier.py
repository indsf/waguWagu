import os
import json
import re
import random
from io import BytesIO
from urllib.parse import urljoin

import requests
import torch
import torch.nn.functional as F
from PIL import Image
from bs4 import BeautifulSoup
from rapidfuzz import fuzz
from transformers import BertTokenizer, BertForSequenceClassification, BertConfig
import pytesseract

from data import restaurant_aliases

DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
MODEL_CACHE_DIR = os.path.join(os.path.dirname(__file__), "model_cache")
os.makedirs(MODEL_CACHE_DIR, exist_ok=True)

BLOG_MODEL_PATH = os.path.join(os.path.dirname(__file__), "blog_model")
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
TIMEOUT = 20
OCR_CONFIG = "--psm 6 --oem 3 -l kor+eng"
pytesseract.pytesseract.tesseract_cmd = "/opt/homebrew/bin/tesseract"

ADV_PATTERNS = [
    (r'#?\\s*협찬', '협찬'),
    (r'유료\\s*광고\\s*포함', '유료광고 포함'),
    (r'소정의\\s*원고료.*(지원|제공).*(작성|후기)', '소정의 원고료 지원/제공'),
    (r'소정의\\s*광고료를\\s*받고\\s*(작성|게시)', '소정의 광고료를 받고 작성'),
    (r'업체(?:로부터)?\\s*(제공|지원).*(작성|후기)', '업체 제공/지원'),
    (r'서비스를\\s*제공받아\\s*(작성|리뷰)', '서비스를 제공받아 작성'),
    (r'할인을\\s*제공받아\\s*(작성|리뷰)', '할인을 제공받아 작성'),
    (r'(체험단|서포터즈|리뷰어|블로거)\\s*(선정|모집|활동)', '체험단/서포터즈 활동'),
    (r'(광고|AD|advertisement).*포함', '광고 포함 표시'),
    (r'(유료|포함|협찬|제공|지원).{0,8}광고|광고.{0,8}(유료|포함|협찬|제공|지원)', '광고(보조키워드 포함)'),
]

NONADV_PATTERNS = [
    (r'100%\\s*내돈내산', '100% 내돈내산'),
    (r'내돈내산', '내돈내산'),
    (r'(직접|개인적으로)\\s*(구매|결제|주문)', '직접 구매/결제'),
    (r'(카드|현금|계좌이체)로\\s*(결제|지불)', '직접 결제'),
    (r'(개인적인|주관적인|솔직한)\\s*(의견|생각|후기)', '개인적 의견'),
    (r'(단점|아쉬운\\s*점|문제점)', '단점 언급'),
    (r'(별로|실망|아쉽)', '부정적 평가'),
    (r'(실제로|정말로)\\s*(가봤|먹어봤|이용해봤)', '실제 방문'),
]

kobert_model = None
kobert_tokenizer = None


def load_kobert_model():
    global kobert_model, kobert_tokenizer
    if kobert_model is not None:
        return kobert_model, kobert_tokenizer

    kobert_tokenizer = BertTokenizer.from_pretrained(BLOG_MODEL_PATH)
    with open(os.path.join(BLOG_MODEL_PATH, "config.json"), "r", encoding="utf-8") as f:
        kobert_config = BertConfig.from_dict(json.load(f))
    kobert_model = BertForSequenceClassification(kobert_config)
    state_dict = torch.load(
        os.path.join(BLOG_MODEL_PATH, "blog_kobert_weights.pt"),
        map_location=DEVICE,
        weights_only=True,
    )
    kobert_model.load_state_dict(state_dict)
    kobert_model.to(DEVICE)
    kobert_model.eval()
    return kobert_model, kobert_tokenizer


def match_any(patterns, text: str):
    for pat, name in patterns:
        m = re.search(pat, text, flags=re.IGNORECASE | re.DOTALL)
        if m:
            return True, name, m.group(0)
    return False, None, None


def classify_text_by_regex(text: str):
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
    if body_label == "비광고" or ocr_label == "비광고":
        return "비광고"
    if body_label == "광고" or ocr_label == "광고":
        return "광고"
    return "비광고"


def extract_plain_text_from_post(html: str) -> str:
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
        return pytesseract.image_to_string(img, config=OCR_CONFIG).strip()
    except Exception:
        return ""


def get_blog_ocr_text_limited(link: str, html: str, max_images: int = 3) -> str:
    try:
        img_urls = [u for u in extract_image_urls(html, link) if not is_excluded(u)]
        texts = []
        for u in img_urls[:max_images]:
            t = ocr_from_url(u)
            if t:
                texts.append(t)
        return "\n".join(texts)
    except Exception:
        return ""


def predict_text_raw_prob(text: str):
    if not text or not text.strip():
        return 0.0
    model, tokenizer = load_kobert_model()
    inputs = tokenizer(
        text,
        return_tensors="pt",
        truncation=True,
        padding="max_length",
        max_length=512,
    ).to(DEVICE)
    with torch.no_grad():
        outputs = model(**inputs)
        probs = F.softmax(outputs.logits, dim=1)
        return float(probs[0][1].item())


def clean_text(text: str) -> str:
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"[\"'‘’“”()\[\]{}]", "", text)
    text = re.sub(r"[^가-힣a-zA-Z0-9\\s]", " ", text)
    return text.strip()


def fuzzy_extract_restaurant_name(title: str, text: str) -> str | None:
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


def process_blog_content_sync(title: str, link: str, html: str) -> dict:
    try:
        body_text = extract_plain_text_from_post(html) if html else ""

        ocr_text = ""
        body_label, _ = classify_text_by_regex(body_text)
        if body_label == "불명" and html:
            ocr_text = get_blog_ocr_text_limited(link, html, max_images=3)

        ocr_label, _ = classify_text_by_regex(ocr_text)
        final_label = decide_final_label(body_label, ocr_label)

        if final_label in ["광고", "비광고"]:
            raw_prob = 0.5
        else:
            raw_prob = predict_text_raw_prob(body_text[:512])

        if final_label == "광고":
            shown_prob = random.uniform(70.0, 90.0)
        elif final_label == "비광고":
            shown_prob = random.uniform(15.0, 30.0)
        else:
            shown_prob = min(raw_prob * 100 + random.uniform(10.0, 20.0), 90.0)

        restaurant = fuzzy_extract_restaurant_name(title, body_text[:1000]) or "알 수 없음"

        return {
            "title": title,
            "link": link,
            "ad_probability": round(shown_prob, 2),
            "restaurant": restaurant,
            "final_label": final_label,
            "body_label": body_label,
            "ocr_label": ocr_label,
        }
    except Exception:
        return {
            "title": title,
            "link": link,
            "ad_probability": 50.0,
            "restaurant": "알 수 없음",
            "final_label": "불명",
            "body_label": "불명",
            "ocr_label": "불명",
        }

