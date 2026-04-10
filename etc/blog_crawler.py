"""
블로그 크롤링 관련 모듈
- 네이버 블로그 검색
- HTML 페치 및 파싱
- 이미지 URL 추출
- 텍스트 추출
"""

import re
import requests
import aiohttp
import asyncio
import time
import random
from typing import List, Tuple, Dict
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed

from config import (
    NAVER_CLIENT_ID, 
    NAVER_CLIENT_SECRET, 
    USER_AGENT, 
    TIMEOUT,
    CACHE_EXPIRY
)

# 전역 캐시
blog_cache = {}

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
        headers = {"User-Agent": USER_AGENT}
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

def fetch_post_html(blog_url: str) -> str:
    """네이버 블로그 iframe 진입"""
    headers = {"User-Agent": USER_AGENT}
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
    return soup.get_text(separator=" ", strip=True)

def extract_image_urls(html: str, base_url: str) -> List[str]:
    """HTML에서 이미지 URL 추출"""
    soup = BeautifulSoup(html, "html.parser")
    urls = []
    
    for img in soup.find_all("img"):
        src = img.get("src")
        if src:
            if src.startswith("http"):
                urls.append(src)
            else:
                urls.append(urljoin(base_url, src))
    return urls

def is_excluded(img_url: str) -> bool:
    """이미지 URL 필터링 (로고, 아이콘 등 제외)"""
    exclude_patterns = [
        r"logo", r"icon", r"profile", r"avatar", 
        r"banner", r"header", r"footer", r"sidebar"
    ]
    return any(re.search(pattern, img_url, re.IGNORECASE) for pattern in exclude_patterns)

def naver_blog_search(query: str, search_strategy: str = "mixed") -> List[Tuple[str, str]]:
    """
    향상된 네이버 OpenAPI 블로그 검색
    
    Args:
        query: 검색어
        search_strategy: 검색 전략
            - "mixed": 관련도순 + 최신순 혼합 (기본값, 추천)
            - "sim": 관련도순만
            - "date": 최신순만  
            - "random": 많이 가져와서 랜덤 선택
    
    Returns:
        List[Tuple[str, str]]: [(title, link), ...] 형태의 결과 리스트
    """
    url = "https://openapi.naver.com/v1/search/blog.json"
    headers = {
        "X-Naver-Client-Id": NAVER_CLIENT_ID,
        "X-Naver-Client-Secret": NAVER_CLIENT_SECRET
    }
    
    all_results = []
    
    try:
        if search_strategy == "mixed":
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
            print(f"✅ 결과: {len(all_results)}개")
    
    except Exception as e:
        print(f"▶▶▶ [블로그 검색 실패] {e}")
        return []
    
    return all_results

async def crawl_blogs_async(blog_list: List[Tuple[str, str]]) -> List[Dict]:
    """비동기로 여러 블로그 크롤링"""
    if not blog_list:
        return []
    
    print(f"🚀 [비동기 크롤링 시작] 총 {len(blog_list)}개 블로그")
    
    async with aiohttp.ClientSession() as session:
        # HTML 페치 (비동기)
        html_tasks = [fetch_post_html_async(session, link) for _, link in blog_list]
        html_results = await asyncio.gather(*html_tasks, return_exceptions=True)
        
        # HTML 결과 정리
        valid_blogs = []
        for i, (title, link) in enumerate(blog_list):
            html = html_results[i]
            if isinstance(html, str) and html.strip():
                valid_blogs.append((title, link, html))
    
    print(f"📄 [HTML 페치 완료] {len(valid_blogs)}/{len(blog_list)}개 성공")
    
    # CPU 집약적 작업은 ThreadPoolExecutor로 처리
    with ThreadPoolExecutor(max_workers=4) as executor:
        # 지연 임포트로 순환 참조 방지
        import ad_classifier
        
        future_to_blog = {
            executor.submit(ad_classifier.process_blog_content_sync, title, link, html): (title, link)
            for title, link, html in valid_blogs
        }
        
        results = []
        for future in as_completed(future_to_blog):
            try:
                result = future.result(timeout=30)  # 30초 타임아웃
                results.append(result)
            except Exception as e:
                title, link = future_to_blog[future]
                print(f"▶▶▶ [처리 실패] {link} → {e}")
                # 기본 결과 추가
                results.append({
                    "title": title,
                    "link": link,
                    "ad_probability": 50.0,
                    "restaurant": "알 수 없음",
                    "final_label": "불명",
                    "body_label": "불명",
                    "ocr_label": "불명"
                })
    
    print(f"✅ [크롤링 완료] 총 {len(results)}개 결과")
    return results

def clean_text(text: str) -> str:
    """텍스트 정리 (HTML 태그 제거, 공백 정리)"""
    # HTML 태그 제거
    clean = re.sub(r'<[^>]+>', '', text)
    # 특수문자 정리
    clean = re.sub(r'[^\w\s가-힣]', ' ', clean)
    # 연속 공백 제거
    clean = re.sub(r'\s+', ' ', clean)
    return clean.strip()