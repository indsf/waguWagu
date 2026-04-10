// src/Result.js

import React, { useState, useEffect, useMemo, useCallback } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import './Results.css';

// 피드백 전송 함수
const submitFeedback = async (type, data) => {
    try {
        const formData = new FormData();
        Object.keys(data).forEach(key => {
            formData.append(key, data[key]);
        });

        const response = await fetch(`http://127.0.0.1:8013/api/feedback/${type}`, {
            method: 'POST',
            body: formData
        });

        if (response.ok) {
            const result = await response.json();
            return { success: true, message: result.message };
        } else {
            return { success: false, message: '피드백 전송 실패' };
        }
    } catch (error) {
        return { success: false, message: '네트워크 오류' };
    }
};

export default function Result() {
    const { state } = useLocation();
    const navigate = useNavigate();
    // Home에서 넘겨준 state.query를 initialQuery로 사용
    const initialQuery = state?.query ?? '';
    const fromDetail = state?.fromDetail || false;
    
    // 컴포넌트 마운트 시 fromDetail 상태를 sessionStorage에 저장
    useEffect(() => {
        if (fromDetail) {
            sessionStorage.setItem('returning_from_detail', 'true');
        }
    }, [fromDetail]);

    // 피드백 관련 상태
    const [feedbackItem, setFeedbackItem] = useState(null); // 현재 피드백 중인 아이템
    const [ratingItem, setRatingItem] = useState(null); // 현재 평가 중인 맛집 아이템

    // 검색어 입력/실행 분리
    const [inputQuery, setInputQuery] = useState(initialQuery);
    const [searchTrigger, setSearchTrigger] = useState({ 
        query: initialQuery, 
        timestamp: fromDetail ? 0 : Date.now() // fromDetail이면 캐시 우선 사용
    });

    // API 결과, 로딩, 필터, 정렬, 페이지
    const [results, setResults] = useState([]);
    const [loading, setLoading] = useState(true);
    const [loadingMessage, setLoadingMessage] = useState('검색을 준비하고 있습니다...');
    const [hideAds, setHideAds] = useState(fromDetail ? (state?.hideAds ?? false) : false);
    const [sortMethod, setSortMethod] = useState(fromDetail ? (state?.sortMethod ?? 'latest') : 'latest');
    const [page, setPage] = useState(fromDetail ? (state?.page ?? 1) : 1);
    const pageSize = 6;

    // 캐시 키 생성
    const getCacheKey = useCallback((query) => `search_results_${query}`, []);
    const getLastSearchKey = useCallback(() => 'last_search_info', []);
    
    // 결과 캐시에서 불러오기
    const loadCachedResults = useCallback((query) => {
        try {
            const cached = sessionStorage.getItem(getCacheKey(query));
            return cached ? JSON.parse(cached) : null;
        } catch {
            return null;
        }
    }, [getCacheKey]);
    
    // 결과 캐시에 저장하기
    // eslint-disable-next-line react-hooks/exhaustive-deps
    const saveCachedResults = useCallback((query, data, currentSortMethod = sortMethod, currentHideAds = hideAds, currentPage = page) => {
        try {
            sessionStorage.setItem(getCacheKey(query), JSON.stringify(data));
            // 마지막 검색 정보도 함께 저장 (현재 상태를 파라미터로 받아서 저장)
            sessionStorage.setItem(getLastSearchKey(), JSON.stringify({
                query,
                timestamp: Date.now(),
                sortMethod: currentSortMethod,
                hideAds: currentHideAds,
                page: currentPage
            }));
        } catch {
            // 캐시 저장 실패 시 무시
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [getCacheKey, getLastSearchKey]);

    // 네비게이션 히스토리 추적
    const trackNavigation = useCallback((query, action = 'search') => {
        try {
            const navHistory = JSON.parse(sessionStorage.getItem('nav_history') || '[]');
            navHistory.push({
                query,
                action,
                timestamp: Date.now(),
                path: '/results'
            });
            // 최근 10개만 유지
            if (navHistory.length > 10) {
                navHistory.shift();
            }
            sessionStorage.setItem('nav_history', JSON.stringify(navHistory));
        } catch {
            // 히스토리 저장 실패 시 무시
        }
    }, []);

    // 브라우저 뒤로가기로 돌아왔는지 확인 (더 간단한 방법)
    const isBackNavigation = useCallback(() => {
        try {
            // returning_from_detail 플래그 확인
            const returningFromDetail = sessionStorage.getItem('returning_from_detail');
            if (returningFromDetail === 'true') {
                // 플래그를 한번 사용하면 삭제
                sessionStorage.removeItem('returning_from_detail');
                return true;
            }
            
            // 히스토리 기반 감지도 유지
            const navHistory = JSON.parse(sessionStorage.getItem('nav_history') || '[]');
            const lastEntry = navHistory[navHistory.length - 1];
            
            if (lastEntry && lastEntry.action === 'detail') {
                const timeSinceLastDetail = Date.now() - lastEntry.timestamp;
                return timeSinceLastDetail < 10000; // 10초 이내
            }
            
            return false;
        } catch {
            return false;
        }
    }, []);

    // 1) 백엔드 호출: /api/crawl_predict (캐시 우선)
    useEffect(() => {
        
        // 검색어가 빈 문자열인 경우에는 "로딩"을 멈추고 바로 리턴
        if (!searchTrigger.query) {
            setLoading(false);
            setResults([]);
            return;
        }

        // 캐시된 결과 먼저 확인
        const cachedResults = loadCachedResults(searchTrigger.query);
        
        // 새로운 검색인지 확인 (타임스탬프가 최근이면 새로운 검색)
        const isNewSearch = searchTrigger.timestamp && (Date.now() - searchTrigger.timestamp) < 3000;
        
        // 브라우저 뒤로가기인지 확인
        const isBack = isBackNavigation();
        
        // 캐시 사용 조건:
        // 1. fromDetail: React Router state로 상세페이지에서 돌아온 경우
        // 2. isBack: 브라우저 뒤로가기 또는 sessionStorage 플래그
        // 3. !searchTrigger.timestamp: 초기 로드 (타임스탬프 없음)
        const shouldUseCache = fromDetail || isBack || !searchTrigger.timestamp;
        
        if (cachedResults && cachedResults.length > 0 && shouldUseCache) {
            setResults(cachedResults);
            setLoading(false);
            
            // 마지막 검색 정보 복원
            try {
                const lastSearchInfo = JSON.parse(sessionStorage.getItem('last_search_info') || '{}');
                if (lastSearchInfo.query === searchTrigger.query) {
                    setSortMethod(lastSearchInfo.sortMethod || 'latest');
                    setHideAds(lastSearchInfo.hideAds || false);
                    setPage(lastSearchInfo.page || 1);
                }
            } catch {
                // 복원 실패 시 무시
            }
            return;
        }

        // 명시적인 새로운 검색이 아니고 캐시가 있으면 사용
        if (!isNewSearch && cachedResults && cachedResults.length > 0) {
            setResults(cachedResults);
            setLoading(false);
            return;
        }
        
        // 새로운 검색이 아닌데 캐시도 없으면 API 호출 안함
        if (!isNewSearch) {
            setLoading(false);
            return;
        }

        // 새로운 검색인 경우에만 검색 액션 추적
        if (isNewSearch) {
            trackNavigation(searchTrigger.query, 'search');
        }

        setLoading(true);
        setLoadingMessage('🔍 관련도 높은 블로그를 검색하고 있습니다...');
        
        const form = new FormData();
        form.append('query', searchTrigger.query);


        // 로딩 메시지 업데이트를 위한 타이머
        const messageTimer = setTimeout(() => {
            setLoadingMessage('블로그 내용을 분석하고 있습니다...');
        }, 2000);

        const analysisTimer = setTimeout(() => {
            setLoadingMessage('AI가 광고 여부를 판별하고 있습니다...');
        }, 5000);

        fetch('http://127.0.0.1:8013/api/crawl_predict', {
            method: 'POST',
            body: form
        })
            .then(res => res.json())
            .then(data => {
                clearTimeout(messageTimer);
                clearTimeout(analysisTimer);
                
                if (data.status === 'ok') {
                    setResults(data.data);
                    // 새로운 검색 결과를 캐시에 저장 (현재 필터/페이지 상태 포함)
                    saveCachedResults(searchTrigger.query, data.data, sortMethod, hideAds, 1);
                } else {
                    setResults([]);
                }
                setPage(1);
                setLoading(false);
            })
            .catch(() => {
                clearTimeout(messageTimer);
                clearTimeout(analysisTimer);
                setResults([]);
                setLoading(false);
                setLoadingMessage('검색 중 오류가 발생했습니다.');
            });
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [searchTrigger.query, searchTrigger.timestamp, fromDetail]);

    // 2) 정렬 + 필터 적용 (백엔드에서 이미 추천 순서 정렬됨)
    const processed = useMemo(() => {
        let arr = hideAds
            ? results.filter(r => r.ad_probability <= 50)
            : [...results];

        // 백엔드에서 이미 추천 3개가 상위에 배치되어 있으므로
        // 사용자 선택 정렬 방식에 따라 전체 리스트를 재정렬
        if (sortMethod === 'latest') {
            // 백엔드 순서 그대로 유지 (추천 3개 + 나머지 관련도순)
            return arr;
        } else if (sortMethod === 'random') {
            // 추천 블로그는 상위 유지, 나머지만 랜덤
            const topRecommended = arr.filter((r, idx) => r.recommendation_count > 0 && idx < 3);
            const others = arr.filter((r, idx) => r.recommendation_count === 0 || idx >= 3);
            
            // 나머지 블로그들만 랜덤 셔플
            for (let i = others.length - 1; i > 0; i--) {
                const j = Math.floor(Math.random() * (i + 1));
                [others[i], others[j]] = [others[j], others[i]];
            }
            
            return [...topRecommended, ...others];
        } else if (sortMethod === 'lowAd') {
            // 추천 블로그는 상위 유지, 나머지만 광고 확률 낮은 순
            const topRecommended = arr.filter((r, idx) => r.recommendation_count > 0 && idx < 3);
            const others = arr.filter((r, idx) => r.recommendation_count === 0 || idx >= 3);
            
            // 나머지 블로그들만 광고 확률 낮은 순 정렬
            others.sort((a, b) => a.ad_probability - b.ad_probability);
            
            return [...topRecommended, ...others];
        }

        return arr;
    }, [results, hideAds, sortMethod]);

    // 3) 페이지네이션
    const totalPages = Math.ceil(processed.length / pageSize);
    const pageItems = useMemo(() => {
        const start = (page - 1) * pageSize;
        return processed.slice(start, start + pageSize);
    }, [processed, page]);

    // 4) HTML 태그 제거 헬퍼
    const stripHtml = useCallback(s => s.replace(/<[^>]+>/g, ''), []);

    // 5) HTML 엔티티 디코딩 헬퍼
    const decodeHtmlEntities = useCallback((str) => {
        const txt = document.createElement('textarea');
        txt.innerHTML = str;
        return txt.value;
    }, []);

    // 6) 재검색 실행
    const handleSearch = useCallback(() => {
        if (!inputQuery.trim()) {
            alert('검색어를 입력해주세요!');
            return;
        }
        // 명시적인 재검색 - 히스토리 업데이트 및 강제 새로운 검색
        const newTimestamp = Date.now();
        trackNavigation(inputQuery, 'search');
        setSearchTrigger({ query: inputQuery, timestamp: newTimestamp });
    }, [inputQuery, trackNavigation]);

    // 광고 판별 피드백 처리
    const handleAdFeedback = useCallback(async (item, isCorrect) => {
        const result = await submitFeedback('ad-classification', {
            blog_url: item.link,
            blog_title: item.title,
            predicted_probability: item.ad_probability / 100,
            is_correct: isCorrect
        });

        if (result.success) {
            alert('✅ 피드백이 저장되었습니다! 감사합니다.');
        } else {
            alert('❌ 피드백 저장에 실패했습니다.');
        }
        setFeedbackItem(null);
    }, []);

    // 맛집 평가 피드백 처리  
    const handleRestaurantFeedback = useCallback(async (restaurantName, rating, visited, blogUrl) => {
        const result = await submitFeedback('restaurant-rating', {
            restaurant_name: restaurantName,
            rating: rating,
            visited: visited,
            blog_url: blogUrl,
            comment: ''
        });

        if (result.success) {
            alert('⭐ 맛집 평가가 저장되었습니다! 감사합니다.');
        } else {
            alert('❌ 평가 저장에 실패했습니다.');
        }
    }, []);

    return (
        <div className="results-root">
            <header className="results-header">
                {/* 로고 클릭 → 홈 */}
                <img
                    src="/minititle.png"
                    alt="로고"
                    className="mini-logo"
                    onClick={() => navigate('/')}
                />

                {/* 검색창 */}
                <div className="search-container">
                    <input
                        type="text"
                        value={inputQuery}
                        onChange={e => setInputQuery(e.target.value)}
                        onKeyDown={e => e.key === 'Enter' && handleSearch()}
                        placeholder="검색어를 입력하세요"
                    />
                    <button onClick={handleSearch}>🔍</button>
                </div>

                {/* 우측 컨트롤: 정렬 + 광고 필터링 토글 */}
                <div className="controls">
                    
                    <select
                        value={sortMethod}
                        onChange={e => setSortMethod(e.target.value)}
                        title="결과 정렬 방식"
                    >
                        <option value="latest">최신순</option>
                        <option value="random">랜덤</option>
                        <option value="lowAd">광고 낮은 순</option>
                    </select>

                    <div className="toggle-container">
                        <label className="switch">
                            <input
                                type="checkbox"
                                checked={hideAds}
                                onChange={e => setHideAds(e.target.checked)}
                            />
                            <span></span>
                        </label>
                        <span className="toggle-text">광고 필터링</span>
                    </div>
                </div>
            </header>

            {loading ? (
                <div className="loading-spinner">
                    <div className="spinner"></div>
                    <div style={{ fontSize: '1.1em', marginTop: 4 }}>
                        {loadingMessage}
                    </div>
                    <div style={{ fontSize: '0.9em', marginTop: 8, color: 'var(--text-muted)' }}>
                        최대 18개의 블로그를 빠른 속도로 분석하고 있습니다!
                    </div>
                </div>
            ) : pageItems.length === 0 ? (
                <p className="no-results">결과가 없습니다.</p>
            ) : (
                <>
                    <ul className="results-list">
                        {pageItems.map((item, idx) => {
                            const noDetail = !item.restaurant || item.restaurant === '알 수 없음';
                            return (
                                <li key={idx} className="results-item">
                                    {/* 블로그 글 제목 */}
                                    <div className="blog-title-container">
                                        <a
                                            href={item.link}
                                            target="_blank"
                                            rel="noopener noreferrer"
                                            className="blog-title"
                                        >
                                            {decodeHtmlEntities(stripHtml(item.title))}
                                        </a>
                                        {/* 추천 배지 */}
                                        {!noDetail && item.recommendation_count > 0 && (
                                            <span className="recommendation-badge">
                                                ⭐ {item.recommendation_count}회 ({item.average_rating}점)
                                            </span>
                                        )}
                                    </div>
                                    
                                    {/* 카드 정보 영역 */}
                                    <div className="card-info">
                                        <div className="card-info-left">
                                            <span className={`restaurant-tag${noDetail ? ' restaurant-tag-none' : ''}`}>
                                                {noDetail ? '🔍 미인식' : `🍽️ ${item.restaurant}`}
                                            </span>
                                        </div>
                                        <div className="card-info-right">
                                            {/* 광고 확률 */}
                                            {!hideAds && (
                                                <div className="pill">
                                                    {item.ad_probability.toFixed(1)}% 광고 확률
                                                </div>
                                            )}
                                        </div>
                                    </div>
                                    
                                    {/* 카드 액션 영역 */}
                                    <div className="card-actions">
                                        <div className="left-actions">
                                            {!noDetail ? (
                                                <button
                                                    className="detail-btn"
                                                    onClick={() => {
                                                        // 상세 페이지 이동 추적
                                                        trackNavigation(searchTrigger.query, 'detail');
                                                        navigate('/information', {
                                                            state: { 
                                                                name: item.restaurant,
                                                                returnQuery: searchTrigger.query,
                                                                returnSortMethod: sortMethod,
                                                                returnHideAds: hideAds,
                                                                returnPage: page
                                                            }
                                                        });
                                                    }}
                                                >
                                                    📍 상세보기
                                                </button>
                                            ) : (
                                                <span className="no-detail-info">📵 정보없음</span>
                                            )}
                                        </div>
                                    
                                        {/* 피드백 버튼들 */}
                                        <div className="feedback-buttons">
                                            {feedbackItem === item.link ? (
                                                <div className="feedback-inline">
                                                    <span className="feedback-question">AI 광고 판별이 정확한가요?</span>
                                                    <div className="feedback-options-inline">
                                                        <button 
                                                            className="feedback-btn-inline feedback-correct"
                                                            onClick={() => handleAdFeedback(item, true)}
                                                            title="정확해요"
                                                        >
                                                            👍 맞음
                                                        </button>
                                                        <button 
                                                            className="feedback-btn-inline feedback-incorrect"
                                                            onClick={() => handleAdFeedback(item, false)}
                                                            title="틀려요"
                                                        >
                                                            👎 틀림
                                                        </button>
                                                    </div>
                                                    <button 
                                                        className="feedback-cancel-btn"
                                                        onClick={() => setFeedbackItem(null)}
                                                        title="취소"
                                                    >
                                                        ✕
                                                    </button>
                                                </div>
                                            ) : (
                                                <>
                                                    <button 
                                                        className="feedback-btn feedback-ad"
                                                        onClick={() => setFeedbackItem(item.link)}
                                                        title="광고 판별 피드백"
                                                    >
                                                        💭 피드백
                                                    </button>
                                                    {!noDetail && (
                                                        <div className="restaurant-rating">
                                                            {ratingItem === item.link ? (
                                                                <div className="rating-inline">
                                                                    <span className="rating-question">해당 정보가 도움이 되셨나요?</span>
                                                                    <div className="rating-stars-inline">
                                                                        {[1, 2, 3, 4, 5].map(star => {
                                                                            const ratingTexts = {
                                                                                1: "별로",
                                                                                2: "그저그래", 
                                                                                3: "보통",
                                                                                4: "좋음",
                                                                                5: "최고"
                                                                            };
                                                                            return (
                                                                                <button
                                                                                    key={star}
                                                                                    className="star-btn-inline"
                                                                                    onClick={() => {
                                                                                        handleRestaurantFeedback(item.restaurant, star, false, item.link);
                                                                                        setRatingItem(null);
                                                                                    }}
                                                                                    title={`${star}점 - ${ratingTexts[star]}`}
                                                                                >
                                                                                    ⭐
                                                                                    <span className="star-number">{star}</span>
                                                                                </button>
                                                                            );
                                                                        })}
                                                                    </div>
                                                                    <button 
                                                                        className="rating-cancel-btn"
                                                                        onClick={() => setRatingItem(null)}
                                                                        title="취소"
                                                                    >
                                                                        ✕
                                                                    </button>
                                                                </div>
                                                            ) : (
                                                                <button 
                                                                    className="feedback-btn rating-btn"
                                                                    onClick={() => setRatingItem(item.link)}
                                                                    title="맛집 평가하기"
                                                                >
                                                                    ⭐ 평가
                                                                </button>
                                                            )}
                                                        </div>
                                                    )}
                                                </>
                                            )}
                                        </div>
                                    </div>
                                </li>
                            );
                        })}
                    </ul>

                    <div className="pagination">
                        <button
                            onClick={() => setPage(p => Math.max(1, p - 1))}
                            disabled={page === 1}
                        >
                            ← 이전
                        </button>
                        <span>
                            {page} / {totalPages}
                        </span>
                        <button
                            onClick={() => setPage(p => Math.min(totalPages, p + 1))}
                            disabled={page === totalPages}
                        >
                            다음 →
                        </button>
                    </div>
                </>
            )}
        </div>
    );
}
