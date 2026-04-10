import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import './FeedbackDashboard.css';

export default function FeedbackDashboard() {
    const [analyticsData, setAnalyticsData] = useState(null);
    const [loading, setLoading] = useState(true);
    const [activeTab, setActiveTab] = useState('overview');
    const navigate = useNavigate();

    useEffect(() => {
        fetchDetailedAnalytics();
    }, []);

    const fetchDetailedAnalytics = async () => {
        try {
            const response = await fetch('http://127.0.0.1:8013/api/feedback/detailed-analytics');
            const data = await response.json();
            
            if (data.status === 'success') {
                setAnalyticsData(data.data);
            }
        } catch (error) {
            console.error('상세 분석 데이터 로드 실패:', error);
        } finally {
            setLoading(false);
        }
    };

    if (loading) {
        return (
            <div className="dashboard-loading">
                <div className="spinner"></div>
                <div>상세 분석 데이터를 불러오는 중...</div>
            </div>
        );
    }

    if (!analyticsData) {
        return (
            <div className="dashboard-error">
                분석 데이터를 불러올 수 없습니다.
            </div>
        );
    }

    const { summary, ad_analysis, restaurant_analysis, temporal_analysis, popular_restaurants } = analyticsData;

    // 차트 컴포넌트
    const BarChart = ({ data, title, color = "#3b82f6" }) => (
        <div className="chart-container">
            <h3>{title}</h3>
            <div className="bar-chart">
                {Object.entries(data).map(([key, value]) => {
                    const maxValue = Math.max(...Object.values(data));
                    const percentage = maxValue > 0 ? (value / maxValue) * 100 : 0;
                    return (
                        <div key={key} className="bar-item">
                            <div className="bar-label">{key}</div>
                            <div className="bar-container">
                                <div 
                                    className="bar-fill" 
                                    style={{ 
                                        width: `${percentage}%`, 
                                        backgroundColor: color 
                                    }}
                                ></div>
                                <span className="bar-value">{value}</span>
                            </div>
                        </div>
                    );
                })}
            </div>
        </div>
    );

    const PieChart = ({ data, title }) => {
        const total = Object.values(data).reduce((sum, val) => sum + val, 0);
        const colors = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6'];
        
        return (
            <div className="chart-container">
                <h3>{title}</h3>
                <div className="pie-chart-container">
                    <div className="pie-chart-legend">
                        {Object.entries(data).map(([key, value], index) => {
                            const percentage = total > 0 ? ((value / total) * 100).toFixed(1) : 0;
                            return (
                                <div key={key} className="legend-item">
                                    <div 
                                        className="legend-color" 
                                        style={{ backgroundColor: colors[index % colors.length] }}
                                    ></div>
                                    <span>{key}: {value}개 ({percentage}%)</span>
                                </div>
                            );
                        })}
                    </div>
                </div>
            </div>
        );
    };

    return (
        <div className="feedback-dashboard">
            {/* 헤더 */}
            <header className="dashboard-header">
                <button onClick={() => navigate('/')} className="home-button">
                    🏠 홈으로
                </button>
                <h1>📊 피드백 분석 대시보드</h1>
                <div className="refresh-button" onClick={fetchDetailedAnalytics}>
                    🔄 새로고침
                </div>
            </header>

            {/* 탭 네비게이션 */}
            <nav className="dashboard-tabs">
                <button 
                    className={activeTab === 'overview' ? 'active' : ''}
                    onClick={() => setActiveTab('overview')}
                >
                    📈 개요
                </button>
                <button 
                    className={activeTab === 'ads' ? 'active' : ''}
                    onClick={() => setActiveTab('ads')}
                >
                    🎯 광고 분석
                </button>
                <button 
                    className={activeTab === 'restaurants' ? 'active' : ''}
                    onClick={() => setActiveTab('restaurants')}
                >
                    🍽️ 맛집 분석
                </button>
                <button 
                    className={activeTab === 'trends' ? 'active' : ''}
                    onClick={() => setActiveTab('trends')}
                >
                    📅 시간 패턴
                </button>
            </nav>

            {/* 탭 콘텐츠 */}
            <div className="dashboard-content">
                {activeTab === 'overview' && (
                    <div className="tab-content">
                        <div className="summary-cards">
                            <div className="summary-card">
                                <h3>총 피드백</h3>
                                <div className="card-value">{summary.total_feedbacks}</div>
                                <div className="card-desc">전체 사용자 피드백</div>
                            </div>
                            <div className="summary-card">
                                <h3>광고 판별 정확도</h3>
                                <div className="card-value">{ad_analysis.accuracy}%</div>
                                <div className="card-desc">{ad_analysis.total_evaluations}개 평가 기준</div>
                            </div>
                            <div className="summary-card">
                                <h3>평균 맛집 평점</h3>
                                <div className="card-value">⭐ {restaurant_analysis.average_rating}</div>
                                <div className="card-desc">{restaurant_analysis.total_ratings}개 평가</div>
                            </div>
                            <div className="summary-card">
                                <h3>추천 비율</h3>
                                <div className="card-value">{restaurant_analysis.high_rated_percentage}%</div>
                                <div className="card-desc">4점 이상 평가</div>
                            </div>
                        </div>

                        <div className="charts-grid">
                            <PieChart 
                                data={restaurant_analysis.rating_distribution} 
                                title="🍽️ 맛집 평점 분포" 
                            />
                            <BarChart 
                                data={temporal_analysis.weekly_activity} 
                                title="📅 요일별 활동" 
                                color="#10b981"
                            />
                        </div>

                        <div className="popular-restaurants">
                            <h3>🏆 인기 맛집 TOP 5</h3>
                            <div className="restaurant-list">
                                {popular_restaurants.slice(0, 5).map((restaurant, index) => (
                                    <div key={restaurant.name} className="restaurant-item">
                                        <div className="restaurant-rank">#{index + 1}</div>
                                        <div className="restaurant-info">
                                            <div className="restaurant-name">{restaurant.name}</div>
                                            <div className="restaurant-stats">
                                                ⭐ {restaurant.average_rating} | 
                                                👍 {restaurant.recommendation_count}회 추천 | 
                                                📊 {restaurant.total_ratings}개 평가
                                                {restaurant.visited_count > 0 && (
                                                    <> | 🚶 {restaurant.visited_count}명 방문</>
                                                )}
                                            </div>
                                        </div>
                                    </div>
                                ))}
                            </div>
                        </div>
                    </div>
                )}

                {activeTab === 'ads' && (
                    <div className="tab-content">
                        <div className="summary-cards">
                            <div className="summary-card">
                                <h3>전체 정확도</h3>
                                <div className="card-value">{ad_analysis.accuracy}%</div>
                                <div className="card-desc">AI 광고 판별 정확도</div>
                            </div>
                            <div className="summary-card">
                                <h3>정확한 예측</h3>
                                <div className="card-value">{ad_analysis.correct_predictions}</div>
                                <div className="card-desc">총 {ad_analysis.total_evaluations}개 중</div>
                            </div>
                        </div>

                        <div className="accuracy-breakdown">
                            <h3>🎯 확률대별 정확도 분석</h3>
                            <div className="accuracy-grid">
                                {Object.entries(ad_analysis.probability_range_accuracy).map(([range, data]) => (
                                    <div key={range} className="accuracy-item">
                                        <div className="accuracy-range">{range}</div>
                                        <div className="accuracy-value">{data.accuracy.toFixed(1)}%</div>
                                        <div className="accuracy-count">{data.count}개 평가</div>
                                    </div>
                                ))}
                            </div>
                        </div>
                    </div>
                )}

                {activeTab === 'restaurants' && (
                    <div className="tab-content">
                        <div className="summary-cards">
                            <div className="summary-card">
                                <h3>평균 평점</h3>
                                <div className="card-value">⭐ {restaurant_analysis.average_rating}</div>
                                <div className="card-desc">전체 맛집 평균</div>
                            </div>
                            <div className="summary-card">
                                <h3>실제 방문율</h3>
                                <div className="card-value">{restaurant_analysis.visited_percentage}%</div>
                                <div className="card-desc">{restaurant_analysis.visited_count}명이 실제 방문</div>
                            </div>
                        </div>

                        <div className="charts-grid">
                            <PieChart 
                                data={restaurant_analysis.rating_distribution} 
                                title="⭐ 평점 분포" 
                            />
                        </div>

                        <div className="restaurant-ranking">
                            <h3>🏆 전체 맛집 랭킹</h3>
                            <div className="restaurant-list">
                                {popular_restaurants.map((restaurant, index) => (
                                    <div key={restaurant.name} className="restaurant-item">
                                        <div className="restaurant-rank">#{index + 1}</div>
                                        <div className="restaurant-info">
                                            <div className="restaurant-name">{restaurant.name}</div>
                                            <div className="restaurant-stats">
                                                ⭐ {restaurant.average_rating} | 
                                                👍 {restaurant.recommendation_count}회 추천 | 
                                                📊 {restaurant.total_ratings}개 평가
                                                {restaurant.visited_count > 0 && (
                                                    <> | 🚶 {restaurant.visited_count}명 방문</>
                                                )}
                                            </div>
                                        </div>
                                    </div>
                                ))}
                            </div>
                        </div>
                    </div>
                )}

                {activeTab === 'trends' && (
                    <div className="tab-content">
                        <div className="charts-grid">
                            <BarChart 
                                data={temporal_analysis.hourly_activity} 
                                title="🕐 시간대별 활동" 
                                color="#f59e0b"
                            />
                            <BarChart 
                                data={temporal_analysis.weekly_activity} 
                                title="📅 요일별 활동" 
                                color="#10b981"
                            />
                        </div>

                        <div className="daily-activity">
                            <h3>📈 일별 활동 추이</h3>
                            <div className="daily-chart">
                                {Object.entries(temporal_analysis.daily_activity)
                                    .sort(([a], [b]) => new Date(a) - new Date(b))
                                    .slice(-14) // 최근 14일
                                    .map(([date, count]) => {
                                        const maxDaily = Math.max(...Object.values(temporal_analysis.daily_activity));
                                        const percentage = maxDaily > 0 ? (count / maxDaily) * 100 : 0;
                                        return (
                                            <div key={date} className="daily-bar">
                                                <div className="daily-date">{date.split('-').slice(1).join('/')}</div>
                                                <div className="daily-bar-container">
                                                    <div 
                                                        className="daily-bar-fill" 
                                                        style={{ height: `${percentage}%` }}
                                                    ></div>
                                                </div>
                                                <div className="daily-count">{count}</div>
                                            </div>
                                        );
                                    })}
                            </div>
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
}