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
            
            print(f"💾 [피드백 저장 시도] 타입: {feedback_type}")
            print(f"   📊 데이터: {data}")
            
            feedbacks.append(feedback_entry)
            self._save_feedback(feedbacks)
            
            print(f"✅ 피드백 저장 완료: {feedback_type} (ID: {feedback_entry['id']})")
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
    
    def get_restaurant_recommendation_counts(self) -> Dict[str, int]:
        """맛집별 추천 횟수 반환 (레거시 함수 - 사용 안함)"""
        return {}
    
    def get_blog_recommendation_counts(self) -> Dict[str, int]:
        """블로그 URL별 추천 횟수 반환"""
        feedbacks = self._load_feedback()
        blog_counts = {}
        
        for feedback in feedbacks:
            if feedback.get('type') == 'restaurant_rating':
                data = feedback.get('data', {})
                blog_url = data.get('blog_url', '').strip()
                rating = data.get('rating', 0)
                
                # 4점 이상을 추천으로 간주
                if blog_url and rating >= 4:
                    blog_counts[blog_url] = blog_counts.get(blog_url, 0) + 1
        
        return blog_counts
    
    def get_blog_average_ratings(self) -> Dict[str, Dict]:
        """블로그 URL별 평균 평점과 추천 횟수 반환"""
        feedbacks = self._load_feedback()
        blog_stats = {}
        
        for feedback in feedbacks:
            if feedback.get('type') == 'restaurant_rating':
                data = feedback.get('data', {})
                blog_url = data.get('blog_url', '').strip()
                rating = data.get('rating', 0)
                
                if blog_url and rating > 0:
                    if blog_url not in blog_stats:
                        blog_stats[blog_url] = {
                            'total_ratings': 0,
                            'sum_ratings': 0,
                            'recommendation_count': 0
                        }
                    
                    blog_stats[blog_url]['total_ratings'] += 1
                    blog_stats[blog_url]['sum_ratings'] += rating
                    
                    # 4점 이상을 추천으로 간주
                    if rating >= 4:
                        blog_stats[blog_url]['recommendation_count'] += 1
        
        # 평균 평점 계산
        result = {}
        for blog_url, stats in blog_stats.items():
            if stats['total_ratings'] > 0:
                average_rating = stats['sum_ratings'] / stats['total_ratings']
                result[blog_url] = {
                    'average_rating': round(average_rating, 2),
                    'recommendation_count': stats['recommendation_count'],
                    'total_ratings': stats['total_ratings']
                }
        
        return result
    
    def get_detailed_analytics(self) -> Dict:
        """상세 분석 데이터 반환"""
        feedbacks = self._load_feedback()
        
        # 기본 통계
        total_feedbacks = len(feedbacks)
        ad_feedbacks = [f for f in feedbacks if f.get('type') == 'ad_classification']
        restaurant_feedbacks = [f for f in feedbacks if f.get('type') == 'restaurant_rating']
        
        # 광고 판별 분석
        ad_analysis = self._analyze_ad_feedback(ad_feedbacks)
        
        # 맛집 평가 분석
        restaurant_analysis = self._analyze_restaurant_feedback(restaurant_feedbacks)
        
        # 시간대별 분석
        temporal_analysis = self._analyze_temporal_patterns(feedbacks)
        
        # 인기 맛집 랭킹
        popular_restaurants = self._get_popular_restaurants(restaurant_feedbacks)
        
        return {
            "summary": {
                "total_feedbacks": total_feedbacks,
                "ad_feedbacks_count": len(ad_feedbacks),
                "restaurant_feedbacks_count": len(restaurant_feedbacks)
            },
            "ad_analysis": ad_analysis,
            "restaurant_analysis": restaurant_analysis,
            "temporal_analysis": temporal_analysis,
            "popular_restaurants": popular_restaurants
        }
    
    def _analyze_ad_feedback(self, ad_feedbacks: List[Dict]) -> Dict:
        """광고 판별 피드백 분석"""
        if not ad_feedbacks:
            return {"accuracy": 0, "total_evaluations": 0, "correct_predictions": 0}
        
        correct_predictions = sum(1 for f in ad_feedbacks if f['data'].get('is_correct', False))
        accuracy = (correct_predictions / len(ad_feedbacks)) * 100
        
        # 확률대별 정확도 분석
        probability_ranges = {
            "0-20%": [],
            "20-40%": [],
            "40-60%": [],
            "60-80%": [],
            "80-100%": []
        }
        
        for feedback in ad_feedbacks:
            prob = feedback['data'].get('predicted_probability', 0) * 100
            is_correct = feedback['data'].get('is_correct', False)
            
            if prob <= 20:
                probability_ranges["0-20%"].append(is_correct)
            elif prob <= 40:
                probability_ranges["20-40%"].append(is_correct)
            elif prob <= 60:
                probability_ranges["40-60%"].append(is_correct)
            elif prob <= 80:
                probability_ranges["60-80%"].append(is_correct)
            else:
                probability_ranges["80-100%"].append(is_correct)
        
        range_accuracy = {}
        for range_name, results in probability_ranges.items():
            if results:
                range_accuracy[range_name] = {
                    "accuracy": (sum(results) / len(results)) * 100,
                    "count": len(results)
                }
            else:
                range_accuracy[range_name] = {"accuracy": 0, "count": 0}
        
        return {
            "accuracy": round(accuracy, 2),
            "total_evaluations": len(ad_feedbacks),
            "correct_predictions": correct_predictions,
            "probability_range_accuracy": range_accuracy
        }
    
    def _analyze_restaurant_feedback(self, restaurant_feedbacks: List[Dict]) -> Dict:
        """맛집 평가 피드백 분석"""
        if not restaurant_feedbacks:
            return {"average_rating": 0, "rating_distribution": {}, "high_rated_count": 0}
        
        ratings = [f['data'].get('rating', 0) for f in restaurant_feedbacks]
        average_rating = sum(ratings) / len(ratings)
        
        # 평점 분포
        rating_distribution = {str(i): 0 for i in range(1, 6)}
        for rating in ratings:
            rating_distribution[str(rating)] += 1
        
        # 4점 이상 비율
        high_rated = sum(1 for r in ratings if r >= 4)
        high_rated_percentage = (high_rated / len(ratings)) * 100
        
        # 방문 여부 분석
        visited_count = sum(1 for f in restaurant_feedbacks if f['data'].get('visited', False))
        visited_percentage = (visited_count / len(restaurant_feedbacks)) * 100
        
        return {
            "average_rating": round(average_rating, 2),
            "rating_distribution": rating_distribution,
            "high_rated_count": high_rated,
            "high_rated_percentage": round(high_rated_percentage, 2),
            "visited_count": visited_count,
            "visited_percentage": round(visited_percentage, 2),
            "total_ratings": len(restaurant_feedbacks)
        }
    
    def _analyze_temporal_patterns(self, feedbacks: List[Dict]) -> Dict:
        """시간대별 패턴 분석"""
        from datetime import datetime
        import calendar
        
        if not feedbacks:
            return {"daily_activity": {}, "hourly_activity": {}, "weekly_activity": {}}
        
        daily_activity = {}
        hourly_activity = {str(i): 0 for i in range(24)}
        weekly_activity = {calendar.day_name[i]: 0 for i in range(7)}
        
        for feedback in feedbacks:
            timestamp_str = feedback.get('timestamp', '')
            if timestamp_str:
                try:
                    # ISO 형식 파싱
                    dt = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                    
                    # 일별 활동
                    date_key = dt.strftime('%Y-%m-%d')
                    daily_activity[date_key] = daily_activity.get(date_key, 0) + 1
                    
                    # 시간별 활동
                    hour_key = str(dt.hour)
                    hourly_activity[hour_key] += 1
                    
                    # 요일별 활동
                    weekday_name = calendar.day_name[dt.weekday()]
                    weekly_activity[weekday_name] += 1
                    
                except:
                    continue
        
        return {
            "daily_activity": daily_activity,
            "hourly_activity": hourly_activity,
            "weekly_activity": weekly_activity
        }
    
    def _get_popular_restaurants(self, restaurant_feedbacks: List[Dict]) -> List[Dict]:
        """인기 맛집 랭킹"""
        restaurant_stats = {}
        
        for feedback in restaurant_feedbacks:
            data = feedback.get('data', {})
            restaurant_name = data.get('restaurant_name', '')
            rating = data.get('rating', 0)
            visited = data.get('visited', False)
            
            if restaurant_name:
                if restaurant_name not in restaurant_stats:
                    restaurant_stats[restaurant_name] = {
                        'total_ratings': 0,
                        'sum_ratings': 0,
                        'visited_count': 0,
                        'recommendation_count': 0
                    }
                
                restaurant_stats[restaurant_name]['total_ratings'] += 1
                restaurant_stats[restaurant_name]['sum_ratings'] += rating
                if visited:
                    restaurant_stats[restaurant_name]['visited_count'] += 1
                if rating >= 4:
                    restaurant_stats[restaurant_name]['recommendation_count'] += 1
        
        # 평균 평점과 추천 수 계산
        restaurant_list = []
        for name, stats in restaurant_stats.items():
            avg_rating = stats['sum_ratings'] / stats['total_ratings'] if stats['total_ratings'] > 0 else 0
            restaurant_list.append({
                'name': name,
                'average_rating': round(avg_rating, 2),
                'total_ratings': stats['total_ratings'],
                'recommendation_count': stats['recommendation_count'],
                'visited_count': stats['visited_count']
            })
        
        # 추천 수 기준으로 정렬
        restaurant_list.sort(key=lambda x: (-x['recommendation_count'], -x['average_rating']))
        
        return restaurant_list[:10]  # 상위 10개만 반환

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
                             visited: bool, blog_url: str = "", comment: str = "") -> bool:
    """맛집 평가 피드백 생성"""
    data = {
        "restaurant_name": restaurant_name,
        "rating": rating,  # 1-5점
        "visited": visited,
        "blog_url": blog_url,
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