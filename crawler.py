import os
import re
import time
import random
import hashlib
from typing import List, Tuple
from urllib.parse import urljoin

import requests
import aiohttp
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv()
CLIENT_ID = os.getenv("NAVER_CLIENT_ID", "").strip()
CLIENT_SECRET = os.getenv("NAVER_CLIENT_SECRET", "").strip()
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
TIMEOUT = 20
CACHE_EXPIRY = 300  # 5분

# tt.py 원본의 메모리 캐시를 그대로 분리
blog_cache = {}


def get_cache_key(url: str) -> str:
    return f"blog_{hash(url)}"


def is_cache_valid(timestamp: float) -> bool:
    return time.time() - timestamp < CACHE_EXPIRY


def cleanup_cache() -> int:
    current_time = time.time()
    expired_keys = [
        key for key, (_, timestamp) in blog_cache.items()
        if current_time - timestamp > CACHE_EXPIRY
    ]
    for key in expired_keys:
        del blog_cache[key]
    return len(expired_keys)


def cache_info() -> dict:
    cleanup_cache()
    return {
        "cache_size": len(blog_cache),
        "cache_expiry_seconds": CACHE_EXPIRY,
    }


def naver_blog_search(query: str, search_strategy: str = "sim_random") -> List[Tuple[str, str]]:
    """tt.py 원본 로직 유지: 네이버 블로그 검색"""
    url = "https://openapi.naver.com/v1/search/blog.json"
    headers = {
        "X-Naver-Client-Id": CLIENT_ID,
        "X-Naver-Client-Secret": CLIENT_SECRET,
    }

    all_results = []
    try:
        if search_strategy == "sim_random":
            time_seed = int(time.time() * 1000) % 10000
            query_hash = int(hashlib.md5(query.encode()).hexdigest()[:8], 16) % 1000
            seed = (time_seed + query_hash) % 10000
            random.seed(seed)

            params = {"query": query, "display": 50, "sort": "sim"}
            response = requests.get(url, headers=headers, params=params, timeout=5)
            if response.status_code != 200:
                return []

            result = response.json()
            items = result.get("items", [])
            candidates = [(item["title"], item["link"]) for item in items]

            seen_links = set()
            unique_results = []
            for title, link in candidates:
                if link not in seen_links:
                    unique_results.append((title, link))
                    seen_links.add(link)

            random.shuffle(unique_results)
            all_results = unique_results[:18]

        elif search_strategy == "mixed":
            params_sim = {"query": query, "display": 10, "sort": "sim"}
            response_sim = requests.get(url, headers=headers, params=params_sim, timeout=5)
            if response_sim.status_code == 200:
                result_sim = response_sim.json()
                sim_items = result_sim.get("items", [])
                all_results.extend([(item["title"], item["link"]) for item in sim_items])

            params_date = {"query": query, "display": 12, "sort": "date"}
            response_date = requests.get(url, headers=headers, params=params_date, timeout=5)
            if response_date.status_code == 200:
                result_date = response_date.json()
                date_items = result_date.get("items", [])
                existing_links = {link for _, link in all_results}
                unique_date_items = [
                    (item["title"], item["link"])
                    for item in date_items
                    if item["link"] not in existing_links
                ]
                all_results.extend(unique_date_items[:8])
        else:
            params = {"query": query, "display": 18, "sort": search_strategy}
            response = requests.get(url, headers=headers, params=params, timeout=5)
            if response.status_code != 200:
                return []
            result = response.json()
            items = result.get("items", [])
            all_results = [(item["title"], item["link"]) for item in items]
    except Exception:
        return []

    return all_results[:18]


async def fetch_post_html_async(session: aiohttp.ClientSession, blog_url: str) -> str:
    """비동기 HTML 페치 + 메모리 캐시"""
    cache_key = get_cache_key(blog_url)

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
                if post_response.status != 200:
                    return ""
                result = await post_response.text()
                blog_cache[cache_key] = (result, time.time())
                return result
    except Exception:
        return ""


async def fetch_many_blog_htmls(blog_list: List[Tuple[str, str]]) -> List[Tuple[str, str, str]]:
    """블로그 여러 개의 HTML을 한 번에 비동기로 수집"""
    if not blog_list:
        return []

    async with aiohttp.ClientSession() as session:
        tasks = [fetch_post_html_async(session, link) for _, link in blog_list]
        html_results = await asyncio.gather(*tasks, return_exceptions=True)

    valid_blogs = []
    for i, (title, link) in enumerate(blog_list):
        html = html_results[i]
        if isinstance(html, str) and html.strip():
            valid_blogs.append((title, link, html))
        else:
            valid_blogs.append((title, link, ""))
    return valid_blogs


# asyncio는 import 위치가 아래여도 동작하지만, 가독성을 위해 마지막에 유지
import asyncio

