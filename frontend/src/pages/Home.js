// src/pages/Home.js

import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import SearchBar from '../components/SearchBar';
import QuickTags from '../components/QuickTags';
import ThemeToggle from '../components/ThemeToggle';
import './Home.css';

export default function Home() {
    const [query, setQuery] = useState('');
    const navigate = useNavigate();

    const handleSearch = (searchTerm = query) => {
        const termToSearch = searchTerm || query;
        if (!termToSearch.trim()) {
            alert('검색어를 입력해주세요!');
            return;
        }
        // 검색어가 빈 문자열이 아닌 경우에만 /results 페이지로 state.query를 넘겨줌
        navigate('/results', { state: { query: termToSearch } });
    };

    const handleKeyDown = (e) => {
        if (e.key === 'Enter') handleSearch();
    };

    const handleTagClick = (tag) => {
        setQuery(tag);
        handleSearch(tag);
    };

    return (
        <div className="home-root">
            <ThemeToggle />
            <div className="home-content">
                {/* 로고 */}
                <img
                    src="/title.png"
                    alt="동네 찐 맛집 추천 뭐 먹을까?"
                    className="main-logo"
                />

                {/* 부제목 */}
                <p className="subtitle">
                    지역(동네)별 찐 맛집을 알아보기 위해<br />
                    블로그 글을 기반으로 광고를 필터링하고<br />
                    요약 정보를 제공합니다.
                </p>

                {/* 검색 바 */}
                <SearchBar
                    query={query}
                    setQuery={setQuery}
                    onSearch={handleSearch}
                    onKeyDown={handleKeyDown}
                />

                {/* 퀵 태그 */}
                <QuickTags onSearch={handleTagClick} />
            </div>
        </div>
    );
}
