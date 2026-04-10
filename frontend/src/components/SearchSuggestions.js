import React, { useState, useRef, useEffect, useMemo } from 'react';
import { useSearchHistory } from '../contexts/SearchHistoryContext';
import './SearchSuggestions.css';

export default function SearchSuggestions({ 
    query, 
    onSelect, 
    onClose, 
    isVisible, 
    inputRef 
}) {
    const { searchHistory, getPopularSearches, removeSearchTerm, clearSearchHistory } = useSearchHistory();
    const [selectedIndex, setSelectedIndex] = useState(-1);
    const suggestionsRef = useRef(null);

    // 맛집 데이터 (실제로는 API에서 가져와야 함)
    const restaurantSuggestions = [
        '대구대 맛집', '경산 맛집', '대구 동성로 맛집', '하양 맛집',
        '대구 치킨', '경산 카페', '대구 한식', '하양 중식',
        '대구 이탈리안', '경산 일식', '대구 분식', '하양 카페'
    ];

    // 필터링된 제안사항
    const getFilteredSuggestions = () => {
        if (!query.trim()) {
            return {
                recent: searchHistory.slice(0, 5),
                popular: getPopularSearches().slice(0, 5),
                restaurants: []
            };
        }

        const lowerQuery = query.toLowerCase();
        
        return {
            recent: searchHistory.filter(term => 
                term.toLowerCase().includes(lowerQuery)
            ).slice(0, 3),
            popular: getPopularSearches().filter(term => 
                term.toLowerCase().includes(lowerQuery)
            ).slice(0, 3),
            restaurants: restaurantSuggestions.filter(term => 
                term.toLowerCase().includes(lowerQuery)
            ).slice(0, 5)
        };
    };

    const { recent, popular, restaurants } = getFilteredSuggestions();
    const allSuggestions = useMemo(() => [...recent, ...popular, ...restaurants], [recent, popular, restaurants]);

    // 키보드 네비게이션
    useEffect(() => {
        const handleKeyDown = (e) => {
            if (!isVisible || allSuggestions.length === 0) return;

            switch (e.key) {
                case 'ArrowDown':
                    e.preventDefault();
                    setSelectedIndex(prev => 
                        prev < allSuggestions.length - 1 ? prev + 1 : 0
                    );
                    break;
                case 'ArrowUp':
                    e.preventDefault();
                    setSelectedIndex(prev => 
                        prev > 0 ? prev - 1 : allSuggestions.length - 1
                    );
                    break;
                case 'Enter':
                    e.preventDefault();
                    if (selectedIndex >= 0 && allSuggestions[selectedIndex]) {
                        onSelect(allSuggestions[selectedIndex]);
                    }
                    break;
                case 'Escape':
                    onClose();
                    break;
                default:
                    // 다른 키는 처리하지 않음
                    break;
            }
        };

        if (inputRef?.current) {
            const currentInput = inputRef.current;
            currentInput.addEventListener('keydown', handleKeyDown);
            return () => {
                currentInput.removeEventListener('keydown', handleKeyDown);
            };
        }
    }, [isVisible, selectedIndex, allSuggestions, onSelect, onClose, inputRef]);

    // 외부 클릭 시 닫기
    useEffect(() => {
        const handleClickOutside = (e) => {
            if (suggestionsRef.current && !suggestionsRef.current.contains(e.target) &&
                inputRef?.current && !inputRef.current.contains(e.target)) {
                onClose();
            }
        };

        if (isVisible) {
            document.addEventListener('mousedown', handleClickOutside);
            return () => {
                document.removeEventListener('mousedown', handleClickOutside);
            };
        }
    }, [isVisible, onClose, inputRef]);

    if (!isVisible) return null;

    return (
        <div ref={suggestionsRef} className="search-suggestions">
            {!query.trim() && recent.length > 0 && (
                <div className="suggestion-section">
                    <div className="suggestion-header">
                        <span>최근 검색어</span>
                        <button 
                            className="clear-btn"
                            onClick={(e) => {
                                e.stopPropagation();
                                clearSearchHistory();
                            }}
                        >
                            전체삭제
                        </button>
                    </div>
                    {recent.map((term, index) => (
                        <div 
                            key={`recent-${term}`}
                            className={`suggestion-item ${selectedIndex === index ? 'selected' : ''}`}
                            onClick={() => onSelect(term)}
                            onMouseEnter={() => setSelectedIndex(index)}
                        >
                            <span className="suggestion-icon">🕐</span>
                            <span className="suggestion-text">{term}</span>
                            <button 
                                className="remove-btn"
                                onClick={(e) => {
                                    e.stopPropagation();
                                    removeSearchTerm(term);
                                }}
                            >
                                ✕
                            </button>
                        </div>
                    ))}
                </div>
            )}

            {!query.trim() && popular.length > 0 && (
                <div className="suggestion-section">
                    <div className="suggestion-header">
                        <span>인기 검색어</span>
                    </div>
                    {popular.map((term, index) => (
                        <div 
                            key={`popular-${term}`}
                            className={`suggestion-item ${selectedIndex === (recent.length + index) ? 'selected' : ''}`}
                            onClick={() => onSelect(term)}
                            onMouseEnter={() => setSelectedIndex(recent.length + index)}
                        >
                            <span className="suggestion-icon">🔥</span>
                            <span className="suggestion-text">{term}</span>
                        </div>
                    ))}
                </div>
            )}

            {query.trim() && restaurants.length > 0 && (
                <div className="suggestion-section">
                    <div className="suggestion-header">
                        <span>추천 검색어</span>
                    </div>
                    {restaurants.map((term, index) => (
                        <div 
                            key={`restaurant-${term}`}
                            className={`suggestion-item ${selectedIndex === (recent.length + popular.length + index) ? 'selected' : ''}`}
                            onClick={() => onSelect(term)}
                            onMouseEnter={() => setSelectedIndex(recent.length + popular.length + index)}
                        >
                            <span className="suggestion-icon">🍴</span>
                            <span className="suggestion-text">
                                {term.split(new RegExp(`(${query})`, 'gi')).map((part, i) => 
                                    part.toLowerCase() === query.toLowerCase() ? 
                                        <strong key={i}>{part}</strong> : part
                                )}
                            </span>
                        </div>
                    ))}
                </div>
            )}

            {allSuggestions.length === 0 && query.trim() && (
                <div className="no-suggestions">
                    검색 결과가 없습니다.
                </div>
            )}
        </div>
    );
}