import React, { createContext, useContext, useState } from 'react';

const SearchHistoryContext = createContext();

export const useSearchHistory = () => {
    const context = useContext(SearchHistoryContext);
    if (!context) {
        throw new Error('useSearchHistory must be used within a SearchHistoryProvider');
    }
    return context;
};

export const SearchHistoryProvider = ({ children }) => {
    const [searchHistory, setSearchHistory] = useState(() => {
        // 로컬스토리지에서 검색 기록 불러오기
        try {
            const saved = localStorage.getItem('search-history');
            return saved ? JSON.parse(saved) : [];
        } catch (error) {
            console.error('Failed to load search history:', error);
            return [];
        }
    });

    const [popularSearches, setPopularSearches] = useState(() => {
        // 로컬스토리지에서 인기 검색어 불러오기
        try {
            const saved = localStorage.getItem('popular-searches');
            return saved ? JSON.parse(saved) : {};
        } catch (error) {
            console.error('Failed to load popular searches:', error);
            return {};
        }
    });

    // 검색어 추가
    const addSearchTerm = (term) => {
        if (!term || !term.trim()) return;

        const trimmedTerm = term.trim();
        
        setSearchHistory(prev => {
            // 중복 제거하고 최근 검색어를 맨 앞에 추가
            const filtered = prev.filter(item => item !== trimmedTerm);
            const newHistory = [trimmedTerm, ...filtered];
            
            // 최대 20개까지만 저장
            const limited = newHistory.slice(0, 20);
            
            // 로컬스토리지에 저장
            try {
                localStorage.setItem('search-history', JSON.stringify(limited));
            } catch (error) {
                console.error('Failed to save search history:', error);
            }
            
            return limited;
        });

        // 인기 검색어 카운트 증가
        setPopularSearches(prev => {
            const updated = {
                ...prev,
                [trimmedTerm]: (prev[trimmedTerm] || 0) + 1
            };

            // 로컬스토리지에 저장
            try {
                localStorage.setItem('popular-searches', JSON.stringify(updated));
            } catch (error) {
                console.error('Failed to save popular searches:', error);
            }

            return updated;
        });
    };

    // 검색 기록 삭제
    const removeSearchTerm = (term) => {
        setSearchHistory(prev => {
            const filtered = prev.filter(item => item !== term);
            
            try {
                localStorage.setItem('search-history', JSON.stringify(filtered));
            } catch (error) {
                console.error('Failed to save search history:', error);
            }
            
            return filtered;
        });
    };

    // 모든 검색 기록 삭제
    const clearSearchHistory = () => {
        setSearchHistory([]);
        try {
            localStorage.removeItem('search-history');
        } catch (error) {
            console.error('Failed to clear search history:', error);
        }
    };

    // 인기 검색어 목록 (상위 10개)
    const getPopularSearches = () => {
        return Object.entries(popularSearches)
            .sort(([, a], [, b]) => b - a)
            .slice(0, 10)
            .map(([term]) => term);
    };

    const value = {
        searchHistory,
        popularSearches,
        addSearchTerm,
        removeSearchTerm,
        clearSearchHistory,
        getPopularSearches
    };

    return (
        <SearchHistoryContext.Provider value={value}>
            {children}
        </SearchHistoryContext.Provider>
    );
};