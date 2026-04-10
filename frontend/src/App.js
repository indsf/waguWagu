import React, { useState, useEffect } from 'react';
import { Routes, Route, useLocation } from 'react-router-dom';
import { ThemeProvider } from './contexts/ThemeContext';
import { SearchHistoryProvider } from './contexts/SearchHistoryContext';
import Home from './pages/Home';
import Results from './pages/Results';
import Information from './pages/Information';
import FeedbackDashboard from './pages/FeedbackDashboard';
import FeedbackToggle from './components/FeedbackToggle';
import './App.css';

export default function App() {
    // 사이드바 토글 상태
    const [showService, setShowService] = useState(false);
    const [showContact, setShowContact] = useState(false);

    // 현재 경로 확인 (홈일 때만 네비+사이드바 보임)
    const location = useLocation();
    const isHome = location.pathname === '/';

    // 개발자 정보
    const developers = [
        { name: '구승율', role: '풀스택 개발자',    email: 'role0606@naver.com',    contact: '010-6663-9528' },
        { name: '이인호', role: '알고리즘 설계',       email: 'younghee@example.com',  contact: '010-2345-6789' },
        { name: '김민규', role: '팀장 / AI모델 개발자',    email: 'zmdkfk07@naver.com',   contact: '010-3456-7890' }
    ];

    // 앱 시작시 AI 모델 워밍업
    useEffect(() => {
        const warmupModels = async () => {
            try {
                console.log('🔥 AI 모델 워밍업 시작...');
                const response = await fetch('http://localhost:8013/api/warmup', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                });
                
                if (response.ok) {
                    const result = await response.json();
                    console.log('✅ AI 모델 워밍업 완료:', result.message);
                } else {
                    console.warn('⚠️ AI 모델 워밍업 실패');
                }
            } catch (error) {
                console.warn('⚠️ AI 모델 워밍업 중 오류:', error);
            }
        };

        warmupModels();
    }, []);

    return (
        <ThemeProvider>
            <SearchHistoryProvider>
                <AppContent 
                    showService={showService}
                    setShowService={setShowService}
                    showContact={showContact}
                    setShowContact={setShowContact}
                    isHome={isHome}
                    developers={developers}
                />
            </SearchHistoryProvider>
        </ThemeProvider>
    );
}

function AppContent({ showService, setShowService, showContact, setShowContact, isHome, developers }) {
    return (
        <div className="app-root">
            {isHome && (
                <>
                    {/* 네비게이션 바 */}
                    <nav className="nav-bar">
                        <div className="nav-left" onClick={() => setShowService(true)}>
                            서비스 소개
                        </div>
                        <div className="nav-center">
                        </div>
                        <div className="nav-right" onClick={() => setShowContact(true)}>
                            Contact
                        </div>
                    </nav>

                    {/* 오버레이 */}
                    {(showService || showContact) && (
                        <div
                            className="overlay"
                            onClick={() => {
                                setShowService(false);
                                setShowContact(false);
                            }}
                        />
                    )}

                    {/* 서비스 소개 사이드바 */}
                    <aside className={'sidebar left' + (showService ? ' open' : '')}>
                        <div className="sidebar-content">
                            <button className="close-btn" onClick={() => setShowService(false)}>
                                &times;
                            </button>
                            <h2>서비스 소개</h2>
                            <p>
                                저희 서비스는 블로그 글을 분석해<br />
                                블로그 글에 대한 광고를 판별한 후<br />
                                진짜 맛집만 골라드리는 서비스입니다.<br />
                                맛집을 검색하여 상세정보를 검색해보세요!
                            </p>
                        </div>
                    </aside>

                    {/* Contact 사이드바 */}
                    <aside className={'sidebar right' + (showContact ? ' open' : '')}>
                        <div className="sidebar-content">
                            <button className="close-btn" onClick={() => setShowContact(false)}>
                                &times;
                            </button>
                            <h2>Contact</h2>
                            <div className="dev-list">
                                {developers.map((d, i) => (
                                    <div key={i} className="dev-card">
                                        <strong>{d.name}</strong><br />
                                        {d.role}<br />
                                        {d.email}<br />
                                        {d.contact}
                                    </div>
                                ))}
                            </div>
                        </div>
                    </aside>
                </>
            )}

            {/* 피드백 현황 아이콘 버튼 (홈에서만 표시) */}
            {isHome && <FeedbackToggle />}

            {/* 페이지 라우팅 */}
            <Routes>
                <Route path="/" element={<Home />} />
                <Route path="/results" element={<Results />} />
                <Route path="/information" element={<Information />} />
                <Route path="/feedback-dashboard" element={<FeedbackDashboard />} />
            </Routes>
        </div>
    );
}