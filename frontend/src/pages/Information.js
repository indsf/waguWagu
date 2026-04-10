// src/Information.js

import { useEffect, useState, useRef } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import './Information.css';

// 카카오 지도 API 스크립트 로더
const loadKakaoMapScript = () => {
    return new Promise((resolve, reject) => {
        if (window.kakao && window.kakao.maps) {
            resolve(window.kakao);
            return;
        }
        if (document.getElementById('kakao-map-script')) {
            const intvl = setInterval(() => {
                if (window.kakao && window.kakao.maps) {
                    clearInterval(intvl);
                    resolve(window.kakao);
                }
            }, 50);
            return;
        }
        const script = document.createElement('script');
        script.id = 'kakao-map-script';
        script.src =
            'https://dapi.kakao.com/v2/maps/sdk.js?appkey=1a861a21e933ebb79b537a5418598c75&autoload=false&libraries=services';
        script.async = true;
        script.onload = () => {
            window.kakao.maps.load(() => {
                resolve(window.kakao);
            });
        };
        script.onerror = (error) => reject(error);
        document.head.appendChild(script);
    });
};

export default function Information() {
    const { state } = useLocation();
    const navigate = useNavigate();
    const restaurantName = state?.name || '';
    

    const [info, setInfo] = useState(null);
    const [loading, setLoading] = useState(true);
    const [loadingMessage, setLoadingMessage] = useState('상세정보를 불러오는 중...');
    const [error, setError] = useState('');
    const mapRef = useRef(null);

    // 1) API 호출: 음식점 상세 정보 가져오기
    useEffect(() => {
        if (!restaurantName) {
            setError('잘못된 접근입니다.');
            setLoading(false);
            return;
        }
        setLoading(true);
        setLoadingMessage('🔍 기본 정보를 불러오는 중...');

        // 로딩 메시지를 단계별로 업데이트
        const messageTimer1 = setTimeout(() => {
            setLoadingMessage('📊 감성 분석 중...');
        }, 1000);

        const messageTimer2 = setTimeout(() => {
            setLoadingMessage('📝 리뷰를 분석하는 중...');
        }, 2500);

        const messageTimer3 = setTimeout(() => {
            setLoadingMessage('🤖 AI가 리뷰를 요약하는 중...');
        }, 4000);

        const messageTimer4 = setTimeout(() => {
            setLoadingMessage('🔍 블로그 정보를 확인하는 중...');
        }, 6000);

        fetch(`http://127.0.0.1:8013/api/restaurant/${encodeURIComponent(restaurantName)}`)
            .then((res) => res.json())
            .then((data) => {
                console.log("🍴 restaurant_detail 응답:", data);
                // 모든 타이머 정리
                clearTimeout(messageTimer1);
                clearTimeout(messageTimer2);
                clearTimeout(messageTimer3);
                clearTimeout(messageTimer4);
                
                if (data.status === 'ok') {
                    setInfo(data.data);
                } else {
                    setError(data.detail || '음식점 정보를 가져올 수 없습니다.');
                }
            })
            .catch((err) => {
                console.error("❌ restaurant_detail fetch error:", err);
                // 모든 타이머 정리
                clearTimeout(messageTimer1);
                clearTimeout(messageTimer2);
                clearTimeout(messageTimer3);
                clearTimeout(messageTimer4);
                setError('데이터를 불러오지 못했습니다.');
            })
            .finally(() => setLoading(false));
    }, [restaurantName]);

    // 2) 카카오 지도 렌더링 (16:9 비율로 고정)
    useEffect(() => {
        if (!info || !info.address) return;
        loadKakaoMapScript().then((kakao) => {
            const container = mapRef.current;
            if (!container) return;
            container.innerHTML = '';
            const geocoder = new kakao.maps.services.Geocoder();
            geocoder.addressSearch(info.address, function (result, status) {
                if (status === kakao.maps.services.Status.OK) {
                    const coords = new kakao.maps.LatLng(result[0].y, result[0].x);
                    const mapOption = {
                        center: coords,
                        level: 3,
                    };
                    const map = new kakao.maps.Map(container, mapOption);
                    const marker = new kakao.maps.Marker({
                        map: map,
                        position: coords,
                    });
                    const iwContent = `<div style="padding:6px 12px;font-size:1rem;"><b>${info.name}</b></div>`;
                    const infowindow = new kakao.maps.InfoWindow({
                        content: iwContent,
                    });
                    infowindow.open(map, marker);
                } else {
                    container.innerHTML = "<span class='map-error'>주소를 찾을 수 없습니다.</span>";
                }
            });
        });
    }, [info]);

    // 3) 해시태그 섹션 (빈도수 높은 순서대로 최대 5개씩 표시)
    const renderHashtags = () => {
        if (!info?.hashtags) return null;
        const { positive, negative } = info.hashtags;

        const positiveArr = positive || [];
        const negativeArr = negative || [];

        // 배열에서 빈도수 집계 → 빈도수 내림차순 정렬 → 상위 5개 반환
        const topFiveDistinct = (arr) => {
            const freq = {};
            arr.forEach((tag) => {
                freq[tag] = (freq[tag] || 0) + 1;
            });
            return Object.keys(freq)
                .sort((a, b) => freq[b] - freq[a])
                .slice(0, 5);
        };

        const topPos = topFiveDistinct(positiveArr);
        const topNeg = topFiveDistinct(negativeArr);

        return (
            <div className="hashtag-section">
                <div className="hashtag-block">
                    <div className="hashtag-title positive">👍 긍정 해시태그</div>
                    <div className="hashtag-list">
                        {topPos.length > 0
                            ? topPos.map((tag, idx) => (
                                  <span key={idx} className="hashtag-tag positive-tag">
                                      {tag}
                                  </span>
                              ))
                            : <span className="hashtag-none">-</span>}
                    </div>
                </div>
                <div className="hashtag-block">
                    <div className="hashtag-title negative">👎 부정 해시태그</div>
                    <div className="hashtag-list">
                        {topNeg.length > 0
                            ? topNeg.map((tag, idx) => (
                                  <span key={idx} className="hashtag-tag negative-tag">
                                      {tag}
                                  </span>
                              ))
                            : <span className="hashtag-none">-</span>}
                    </div>
                </div>
            </div>
        );
    };

    // 4) 감성점수 시각화 (간단하고 직관적으로 개선)
    const renderSentimentVisualization = () => {
        if (!info) return null;

        const numericScore = info.sentiment_score ?? 0;    // 0~1000 범위
        const ratioText = info.sentiment_ratio_text || ''; // "전국 평균보다 X배 더 긍정적이에요!"
        
        // 실제 API 데이터 구조 전체 확인
        console.log("🍴 전체 음식점 데이터:", info);
        
        // 리뷰 개수 관련 필드들 상세 확인
        const possibleReviewFields = {
            review_count: info.review_count,
            total_reviews: info.total_reviews, 
            reviews: info.reviews,
            review_num: info.review_num,
            reviewCount: info.reviewCount,
            total_review: info.total_review,
            review_cnt: info.review_cnt,
            cnt: info.cnt,
            count: info.count
        };
        
        console.log("📊 가능한 리뷰 카운트 필드들:", possibleReviewFields);
        
        // 실제 유효한 숫자 값 찾기
        let reviewCount = 0;
        for (const [key, value] of Object.entries(possibleReviewFields)) {
            if (typeof value === 'number' && value > 0) {
                reviewCount = value;
                console.log(`✅ 발견된 리뷰 카운트 필드: ${key} = ${value}`);
                break;
            }
        }
        
        // 숫자가 없으면 문자열이나 다른 형태 확인
        if (reviewCount === 0) {
            for (const [key, value] of Object.entries(possibleReviewFields)) {
                if (value && typeof value === 'string' && !isNaN(parseInt(value))) {
                    reviewCount = parseInt(value);
                    console.log(`✅ 문자열에서 발견된 리뷰 카운트: ${key} = ${value} → ${reviewCount}`);
                    break;
                }
            }
        }
        
        console.log("🎯 최종 리뷰 카운트:", reviewCount);

        let level = 1;
        if (numericScore >= 1000) level = 5;
        else if (numericScore >= 500) level = 4;
        else if (numericScore >= 300) level = 3;
        else if (numericScore >= 100) level = 2;
        
        const levelLabels = {
            1: { label: '아쉬움', color: '#FF6B6B', icon: '😞', stars: 1 },
            2: { label: '보통', color: '#FFA726', icon: '😐', stars: 2 },
            3: { label: '만족', color: '#66BB6A', icon: '😊', stars: 3 },
            4: { label: '추천', color: '#42A5F5', icon: '😍', stars: 4 },
            5: { label: '인기', color: '#FFD700', icon: '🔥', stars: 5 },
        };

        const currentLevel = levelLabels[level];
        
        // 점수 체계 개선: 더 합리적인 분포로 조정
        let displayScore;
        if (level === 1) displayScore = Math.round(30 + (numericScore / 100) * 20); // 30-50점
        else if (level === 2) displayScore = Math.round(50 + ((numericScore - 100) / 200) * 15); // 50-65점
        else if (level === 3) displayScore = Math.round(65 + ((numericScore - 300) / 200) * 15); // 65-80점
        else if (level === 4) displayScore = Math.round(80 + ((numericScore - 500) / 500) * 15); // 80-95점
        else displayScore = Math.round(95 + Math.min(5, (numericScore - 1000) / 200)); // 95-100점
        
        displayScore = Math.max(30, Math.min(100, displayScore)); // 30-100 범위 제한
        
        // 별점 렌더링
        const renderStars = () => {
            return Array.from({length: 5}, (_, i) => (
                <span key={i} className={`star ${i < currentLevel.stars ? 'filled' : 'empty'}`}>
                    ⭐
                </span>
            ));
        };

        return (
            <div className="sentiment-visualization">
                {/* 점수/인사이트 가로 배치 컨테이너 */}
                <div className="score-insights-row">
                    {/* 메인 리뷰 스코어 카드 - 절반 크기 */}
                    <div className="review-score-card-compact">
                        <div className="score-title-section">
                            <h4>종합 리뷰 점수</h4>
                            <p>AI가 분석한 전체 리뷰의 종합 평가입니다</p>
                        </div>
                        
                        <div className="score-header-compact">
                            <div className="score-badge-compact" style={{backgroundColor: currentLevel.color}}>
                                <span className="badge-icon">{currentLevel.icon}</span>
                                <span className="badge-text">{currentLevel.label}</span>
                            </div>
                            <div className="score-value">
                                <span className="score-number">{displayScore}</span>
                                <span className="score-total">/100</span>
                            </div>
                        </div>
                        
                        <div className="score-stars-compact">
                            {renderStars()}
                            <span className="stars-label">{currentLevel.stars}/5</span>
                        </div>
                        
                        <div className="score-progress">
                            <div className="progress-track">
                                <div 
                                    className="progress-fill" 
                                    style={{
                                        width: `${displayScore}%`,
                                        backgroundColor: currentLevel.color
                                    }}
                                ></div>
                            </div>
                        </div>
                        
                        {ratioText && (
                            <div className="score-special-insight">
                                <div className="special-insight-icon">🎯</div>
                                <div className="special-insight-text">{ratioText}</div>
                            </div>
                        )}
                    </div>

                    {/* 리뷰 인사이트 - 절반 크기 */}
                    <div className="review-insights-compact">
                        <div className="insight-header-compact">
                            <h4>리뷰 인사이트</h4>
                        </div>
                        
                        <div className="insights-grid-compact">
                            <div className="insight-card-compact">
                                <div className="insight-icon">📊</div>
                                <div className="insight-content">
                                    <div className="insight-number">
                                        {reviewCount > 0 ? reviewCount.toLocaleString() : '분석중'}
                                    </div>
                                    <div className="insight-label">전체 리뷰</div>
                                </div>
                            </div>
                            
                            <div className="insight-card-compact">
                                <div className="insight-icon">🎯</div>
                                <div className="insight-content">
                                    <div className="insight-number">{Math.round((displayScore/100) * 10)}/10</div>
                                    <div className="insight-label">추천 지수</div>
                                </div>
                            </div>
                            
                            <div className="insight-card-compact">
                                <div className="insight-icon">🏆</div>
                                <div className="insight-content">
                                    <div className="insight-number">Top {Math.round((100-displayScore)/2)}%</div>
                                    <div className="insight-label">카테고리 순위</div>
                                </div>
                            </div>
                            
                            <div className="insight-card-compact">
                                <div className="insight-icon">🔥</div>
                                <div className="insight-content">
                                    <div className="insight-number">{level >= 4 ? '인기' : level >= 3 ? '보통' : '발굴'}</div>
                                    <div className="insight-label">인기도</div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
                
                {/* 해시태그 섹션 - 독립적인 박스로 분리 */}
                <div className="hashtag-box">
                    <div className="hashtag-header">
                        <h4>해시태그</h4>
                    </div>
                    {renderHashtags()}
                </div>
            </div>
        );
    };

    // 5) 리뷰 요약 박스 (KoBART 기반)
    const renderSummaryBox = () => {
        if (!info || !info.kobart_summary) return null;
        const { positive, negative, overall } = info.kobart_summary;
        return (
            <div className="summary-all-wrap">
                <div className="summary-section">
                    <div className="summary-title positive">👍 긍정 리뷰 요약</div>
                    <div className="summary-content">{positive || '정보 없음'}</div>
                </div>
                <div className="summary-section">
                    <div className="summary-title negative">👎 부정 리뷰 요약</div>
                    <div className="summary-content">{negative || '정보 없음'}</div>
                </div>
                <div className="summary-section">
                    <div className="summary-title overall">📊 전체 리뷰 요약</div>
                    <div className="summary-content">{overall || '정보 없음'}</div>
                </div>
            </div>
        );
    };

    return (
        <div className="info-root">
            {/* 상단 로고 + 음식점명 */}
            <div className="info-topbar">
                <img
                    src="/minititle.png"
                    alt="로고"
                    className="mini-logo"
                    onClick={() => navigate('/')}
                />
                {restaurantName && (
                    <div className="restaurant-chip strong">
                        <span className="restaurant-icon">🍽️</span>
                        <span className="restaurant-chip-name">{restaurantName}</span>
                    </div>
                )}
            </div>

            {/* 검은색 가로줄 추가 */}
            <div className="divider"></div>

            {loading ? (
                <div className="loading-spinner">
                    <div className="spinner"></div>
                    <div style={{ fontSize: '1.1em', marginTop: 4 }}>
                        {loadingMessage}
                    </div>
                    <div style={{ fontSize: '0.9em', marginTop: 8, color: 'var(--text-muted)' }}>
                        리뷰 데이터를 AI로 분석하고 있습니다!
                    </div>
                </div>
            ) : error ? (
                <div className="error-msg">{error}</div>
            ) : info ? (
                <div className="info-main">
                    {/* 좌측: 지도 + 가게정보 */}
                    <div className="info-map-col">
                        {/* 가게 기본 정보 카드 */}
                        <div className="restaurant-info-card">
                            <div className="restaurant-header">
                                <div className="restaurant-icon">🍽️</div>
                                <div className="restaurant-details">
                                    <h3 className="restaurant-name">{info.name}</h3>
                                    <p className="restaurant-category">{info.category || '카테고리 정보 없음'}</p>
                                </div>
                            </div>
                            
                            <div className="restaurant-info-grid">
                                <div className="info-item">
                                    <div className="info-icon">📍</div>
                                    <div className="info-content">
                                        <div className="info-label">주소</div>
                                        <div className="info-value">{info.address || '주소 정보 없음'}</div>
                                    </div>
                                </div>
                                
                                {info.naver_place && (
                                    <div className="info-item">
                                        <div className="info-icon">🔗</div>
                                        <div className="info-content">
                                            <div className="info-label">네이버 플레이스</div>
                                            <div className="info-value">
                                                <a href={info.naver_place} target="_blank" rel="noopener noreferrer" className="info-link">
                                                    상세 페이지 보기
                                                </a>
                                            </div>
                                        </div>
                                    </div>
                                )}
                            </div>
                        </div>

                        {/* 지도 카드 */}
                        <div className="map-card">
                            <div className="map-header">
                                <h4>위치 정보</h4>
                            </div>
                            <div className="map-wrapper">
                                <div ref={mapRef} className="info-map"></div>
                            </div>
                        </div>
                    </div>

                    {/* 우측: 리뷰 평가 · 리뷰 요약 · 리뷰 인사이트(해시태그 포함) */}
                    <div className="info-right">
                        <div className="info-box sentiment">{renderSentimentVisualization()}</div>
                        <div className="info-box summary">{renderSummaryBox()}</div>
                    </div>
                </div>
            ) : null}
        </div>
    );
}
