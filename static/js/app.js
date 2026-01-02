/**
 * 카드 명세서 분석 프로그램 JavaScript
 */

// Toast 알림
function showToast(message, type = 'success') {
    const toast = document.getElementById('toast');
    if (!toast) return;
    
    toast.textContent = message;
    toast.className = 'toast show' + (type === 'error' ? ' error' : '');
    
    setTimeout(() => {
        toast.className = 'toast';
    }, 3000);
}

// 금액 포맷팅
function formatCurrency(amount) {
    return '₩' + amount.toLocaleString('ko-KR');
}

// 날짜 포맷팅 (YYYYMMDD -> YYYY.MM.DD)
function formatDate(dateStr) {
    if (!dateStr || dateStr.length !== 8) return dateStr;
    return `${dateStr.slice(0, 4)}.${dateStr.slice(4, 6)}.${dateStr.slice(6, 8)}`;
}

// API 호출 헬퍼
async function api(url, options = {}) {
    const defaultOptions = {
        headers: {
            'Content-Type': 'application/json'
        }
    };
    
    try {
        const response = await fetch(url, { ...defaultOptions, ...options });
        const data = await response.json();
        
        if (!response.ok) {
            throw new Error(data.error || '오류가 발생했습니다');
        }
        
        return data;
    } catch (error) {
        showToast(error.message, 'error');
        throw error;
    }
}

// 디바운스
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

// 페이지 로드 시 초기화
document.addEventListener('DOMContentLoaded', () => {
    // 검색 입력 디바운스
    const searchInput = document.querySelector('.search-input');
    if (searchInput) {
        searchInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                e.target.form.submit();
            }
        });
    }
    
    // Escape 키로 입력 취소
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            document.activeElement.blur();
        }
    });
});

// 확인 대화상자
function confirmAction(message) {
    return confirm(message);
}

// 차트 공통 레이아웃
const chartLayout = {
    paper_bgcolor: 'transparent',
    plot_bgcolor: 'transparent',
    font: { 
        color: '#e2e8f0', 
        family: 'Pretendard, -apple-system, sans-serif' 
    },
    margin: { t: 30, b: 40, l: 50, r: 30 }
};

// 차트 공통 설정
const chartConfig = {
    responsive: true,
    displayModeBar: false
};
