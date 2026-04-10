"""
사용자 피드백 시스템
- 간단한 로컬 파일 기반 저장
- 실시간 분석 및 모델 개선
"""

import json
import pandas as pd
from datetime import datetime
from typing import Dict, List, Optional
import os

class FeedbackManager:
    def __init__(self, data_path: str = "./feedback_data"):
        self.data_path = data_path
        os.makedirs(data_path, exist_ok=True)
        self.feedback_file = os.path.join(data_path, "user_feedback.json")
        
        # 피드백 데이터 초기화
        if not os.path.exists(self.feedback_file):
            self._save_feedback([])
    
    def add_feedback(self, feedback_type: str, data: Dict) -> bool:
        """피드백 추가"""
        try:
            feedbacks = self._load_feedback()
            
            feedback_entry = {
                "id": len(feedbacks) + 1,
                "type": feedback_type,
                "timestamp": datetime.now().isoformat(),
                "data": data
            }
            
            feedbacks.append(feedback_entry)
            self._save_feedback(feedbacks)
            
            print(f"✅ 피드백 저장: {feedback_type}")
            return True
        except Exception as e:
            print(f"❌ 피드백 저장 실패: {e}")
            return False
    
    def get_feedback_stats(self) -> Dict:
        """피드백 통계 반환"""
        feedbacks = self._load_feedback()
        
        if not feedbacks:
            return {"total": 0, "by_type": {}}
        
        df = pd.DataFrame(feedbacks)
        
        stats = {
            "total": len(feedbacks),
            "by_type": df['type'].value_counts().to_dict(),
            "recent_count": len(df[df['timestamp'] >= datetime.now().replace(hour=0, minute=0, second=0).isoformat()]),
        }
        
        return stats
    
    def get_ad_classification_feedback(self) -> List[Dict]:
        """광고 판별 피드백만 추출"""
        feedbacks = self._load_feedback()
        return [f for f in feedbacks if f['type'] == 'ad_classification']
    
    def get_restaurant_rating_feedback(self) -> List[Dict]:
        """맛집 평가 피드백만 추출"""
        feedbacks = self._load_feedback()
        return [f for f in feedbacks if f['type'] == 'restaurant_rating']
    
    def analyze_feedback_trends(self) -> Dict:
        """피드백 트렌드 분석"""
        feedbacks = self._load_feedback()
        
        if not feedbacks:
            return {}
        
        df = pd.DataFrame(feedbacks)
        df['date'] = pd.to_datetime(df['timestamp']).dt.date
        
        # 일별 피드백 수
        daily_counts = df.groupby('date').size().to_dict()
        
        # 광고 판별 정확도 (사용자 피드백 기반)
        ad_feedbacks = [f for f in feedbacks if f['type'] == 'ad_classification']
        if ad_feedbacks:
            correct_predictions = sum(1 for f in ad_feedbacks if f['data'].get('is_correct', False))
            accuracy = correct_predictions / len(ad_feedbacks) * 100
        else:
            accuracy = 0
        
        return {
            "daily_feedback_counts": {str(k): v for k, v in daily_counts.items()},
            "ad_classification_accuracy": round(accuracy, 2),
            "total_feedback_count": len(feedbacks)
        }
    
    def _load_feedback(self) -> List[Dict]:
        """피드백 데이터 로드"""
        try:
            with open(self.feedback_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return []
    
    def _save_feedback(self, feedbacks: List[Dict]):
        """피드백 데이터 저장"""
        with open(self.feedback_file, 'w', encoding='utf-8') as f:
            json.dump(feedbacks, f, ensure_ascii=False, indent=2)

# 글로벌 피드백 매니저 인스턴스
feedback_manager = FeedbackManager()

# 피드백 타입 정의
class FeedbackType:
    AD_CLASSIFICATION = "ad_classification"  # 광고 판별 피드백
    RESTAURANT_RATING = "restaurant_rating"  # 맛집 평가 피드백  
    SEARCH_SATISFACTION = "search_satisfaction"  # 검색 만족도
    VISIT_REVIEW = "visit_review"  # 실제 방문 후기

def create_ad_feedback(blog_url: str, blog_title: str, predicted_probability: float, 
                      user_says_correct: bool, user_comment: str = "") -> bool:
    """광고 판별 피드백 생성"""
    data = {
        "blog_url": blog_url,
        "blog_title": blog_title,
        "predicted_probability": predicted_probability,
        "is_correct": user_says_correct,
        "user_comment": user_comment
    }
    
    return feedback_manager.add_feedback(FeedbackType.AD_CLASSIFICATION, data)

def create_restaurant_feedback(restaurant_name: str, rating: int, 
                             visited: bool, comment: str = "") -> bool:
    """맛집 평가 피드백 생성"""
    data = {
        "restaurant_name": restaurant_name,
        "rating": rating,  # 1-5점
        "visited": visited,
        "comment": comment
    }
    
    return feedback_manager.add_feedback(FeedbackType.RESTAURANT_RATING, data)

def create_search_feedback(query: str, satisfaction: int, found_useful: bool) -> bool:
    """검색 만족도 피드백 생성"""
    data = {
        "query": query,
        "satisfaction": satisfaction,  # 1-5점
        "found_useful": found_useful
    }
    
    return feedback_manager.add_feedback(FeedbackType.SEARCH_SATISFACTION, data)