# 먹어볼래 (Mukabolrae)

**AI 기반 블로그 광고 판별 & 맛집 추천 플랫폼**

대구대학교 하양캠퍼스 주변 맛집의 블로그 리뷰를 분석하여 광고성 글과 진짜 후기를 구별해주는 웹 서비스입니다.

## 핵심 기능

- **블로그 광고 판별** — KoBERT 모델 + 규칙 기반 하이브리드 방식으로 블로그 글의 광고 확률을 0~100%로 판별
- **리뷰 요약** — KoBART 모델을 활용한 리뷰 자동 요약 (긍정/부정/종합)
- **감성 분석** — 키워드 기반 감성 점수 산출 및 주변 맛집 대비 백분위 랭킹
- **실시간 블로그 크롤링** — 네이버 블로그 검색 API 연동, 비동기 크롤링
- **OCR 분석** — 블로그 이미지 내 텍스트 추출로 광고 문구 탐지
- **피드백 시스템** — 사용자 피드백 수집 및 분석 대시보드

## 기술 스택

| 구분 | 기술 |
|------|------|
| **Frontend** | React 18, React Bootstrap, Chart.js, React Router |
| **Backend** | FastAPI (Python 3.9), Uvicorn |
| **AI/ML** | KoBERT (광고 판별), KoBART (리뷰 요약), PyTorch, Transformers |
| **NLP** | Kiwipiepy (한국어 토크나이저), RapidFuzz, NLTK |
| **크롤링** | BeautifulSoup4, aiohttp, Pytesseract (OCR) |
| **데이터** | Pandas, CSV 기반 데이터 저장 |

## 프로젝트 구조

```
Mukabolrae/
├── backend/                    # FastAPI 백엔드
│   ├── main.py                # 메인 서버 (API 엔드포인트)
│   ├── data.py                # 맛집 데이터베이스 (100+ 식당)
│   ├── feedback_system.py     # 피드백 시스템
│   ├── blog_model/            # KoBERT 광고 판별 모델
│   ├── summary_model/         # KoBART 리뷰 요약 모델
│   ├── processed_reviews.csv  # 리뷰 데이터셋
│   └── store_sentiment_result.csv  # 감성 분석 결과
│
├── frontend/                   # React 프론트엔드
│   ├── src/
│   │   ├── pages/             # 페이지 컴포넌트
│   │   │   ├── Home.js        # 메인 검색 페이지
│   │   │   ├── Results.js     # 검색 결과 페이지
│   │   │   ├── Information.js # 맛집 상세 정보
│   │   │   └── FeedbackDashboard.js  # 피드백 대시보드
│   │   ├── components/        # 재사용 컴포넌트
│   │   └── contexts/          # React Context (테마, 검색 기록)
│   └── package.json
│
├── training/                   # ML 모델 학습 스크립트
│   └── kobart.ipynb           # KoBART 학습 노트북
│
├── etc/                        # 유틸리티 스크립트
└── requirements.txt            # Python 의존성
```

## 설치 및 실행

### 사전 요구사항

- Python 3.9+
- Node.js 14+
- Tesseract OCR
- 네이버 검색 API 키

### Backend

```bash
# 의존성 설치
pip install -r requirements.txt

# 환경변수 설정 (.env 파일 생성)
NAVER_CLIENT_ID=<your-client-id>
NAVER_CLIENT_SECRET=<your-client-secret>

# 서버 실행
python backend/main.py
# http://127.0.0.1:8013
```

### Frontend

```bash
cd frontend
npm install
npm start
# http://localhost:3000
```

### ML 모델

모델 가중치 파일(`.pt`, `.safetensors`)은 용량이 크기 때문에 Git에 포함되지 않습니다.
별도로 다운로드하여 다음 경로에 배치해야 합니다:

- `backend/blog_model/` — KoBERT 광고 판별 모델
- `backend/summary_model/` — KoBART 리뷰 요약 모델

## API 엔드포인트

| Method | Endpoint | 설명 |
|--------|----------|------|
| GET | `/health` | 서버 상태 확인 |
| POST | `/api/warmup` | AI 모델 사전 로딩 |
| POST | `/api/crawl_predict` | 블로그 크롤링 & 광고 판별 |
| GET | `/api/restaurant/{name}` | 맛집 상세 정보 조회 |
| POST | `/api/feedback/*` | 사용자 피드백 제출 |
| GET | `/api/feedback/stats` | 피드백 통계 |

## 팀원

| 이름 | 역할 |
|------|------|
| 구승율 | Full-stack 개발 |
| 김민규 | 팀장 / AI 모델 개발 |
| 이인호 | 알고리즘 설계 |
