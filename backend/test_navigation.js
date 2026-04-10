// 네비게이션 히스토리 추적 테스트
// 브라우저 콘솔에서 실행하여 테스트

// 테스트 데이터 설정
sessionStorage.clear();

// 검색 시뮬레이션
const trackNavigation = (query, action = 'search') => {
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
        console.log('Navigation tracked:', { query, action });
    } catch {
        console.error('Failed to track navigation');
    }
};

// 브라우저 뒤로가기로 돌아왔는지 확인
const isBackNavigation = (currentQuery) => {
    try {
        const navHistory = JSON.parse(sessionStorage.getItem('nav_history') || '[]');
        const lastEntry = navHistory[navHistory.length - 1];
        
        // 마지막 액션이 'detail'이고 현재 query와 일치하면 뒤로가기로 간주
        if (lastEntry && lastEntry.action === 'detail' && lastEntry.query === currentQuery) {
            return true;
        }
        
        // 마지막 2개 엔트리를 확인하여 detail -> search 패턴인지 확인
        if (navHistory.length >= 2) {
            const secondLast = navHistory[navHistory.length - 2];
            return lastEntry.action === 'detail' && 
                   secondLast.action === 'search' && 
                   secondLast.query === currentQuery;
        }
        
        return false;
    } catch {
        return false;
    }
};

// 테스트 시나리오
console.log('=== 네비게이션 추적 테스트 시작 ===');

// 1. 검색
trackNavigation('대구대 미즈컨테이너', 'search');
console.log('1. 검색 후 히스토리:', JSON.parse(sessionStorage.getItem('nav_history')));

// 2. 상세페이지 이동
trackNavigation('대구대 미즈컨테이너', 'detail');
console.log('2. 상세페이지 이동 후 히스토리:', JSON.parse(sessionStorage.getItem('nav_history')));

// 3. 뒤로가기 확인
const backCheck1 = isBackNavigation('대구대 미즈컨테이너');
console.log('3. 뒤로가기 감지:', backCheck1, '(예상: true)');

// 4. 새로운 검색
trackNavigation('다른 검색어', 'search');
const backCheck2 = isBackNavigation('다른 검색어');
console.log('4. 새로운 검색에서 뒤로가기 감지:', backCheck2, '(예상: false)');

console.log('=== 테스트 완료 ===');
console.log('최종 히스토리:', JSON.parse(sessionStorage.getItem('nav_history')));