import React, { useState, useRef } from 'react';
import { useSearchHistory } from '../contexts/SearchHistoryContext';
import SearchSuggestions from './SearchSuggestions';

export default function SearchBar({ query, setQuery, onSearch, onKeyDown }) {
    const { addSearchTerm } = useSearchHistory();
    const [showSuggestions, setShowSuggestions] = useState(false);
    const inputRef = useRef(null);

    const handleSearch = () => {
        if (query.trim()) {
            addSearchTerm(query.trim());
            setShowSuggestions(false);
            onSearch();
        }
    };

    const handleKeyDown = (e) => {
        if (e.key === 'Enter') {
            e.preventDefault(); // 기본 동작 방지
            handleSearch();
        }
        if (onKeyDown) {
            onKeyDown(e);
        }
    };

    const handleSuggestionSelect = (suggestion) => {
        setQuery(suggestion);
        addSearchTerm(suggestion);
        setShowSuggestions(false);
        // suggestion을 직접 전달하여 상태 업데이트 지연 문제 해결
        if (suggestion.trim()) {
            // Home 컴포넌트의 navigate 함수를 직접 호출하기 위해 onSearch에 suggestion 전달
            onSearch(suggestion);
        }
    };

    const handleInputFocus = () => {
        setShowSuggestions(true);
    };

    const handleInputChange = (e) => {
        setQuery(e.target.value);
        setShowSuggestions(true);
    };

    return (
        <div className="search-bar-container">
            <div className="search-bar">
                <input
                    ref={inputRef}
                    type="text"
                    value={query}
                    placeholder="예: 대구대 무한폭식"
                    onChange={handleInputChange}
                    onKeyDown={handleKeyDown}
                    onFocus={handleInputFocus}
                />
                <button onClick={handleSearch}>🔍</button>
            </div>
            <SearchSuggestions
                query={query}
                onSelect={handleSuggestionSelect}
                onClose={() => setShowSuggestions(false)}
                isVisible={showSuggestions}
                inputRef={inputRef}
            />
        </div>
    );
}