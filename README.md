# PlaceOpt Internal Console — Wave 1

## 프로젝트 개요

**PlaceOpt**는 네이버 플레이스 마케팅 운영팀을 위한 **내부 운영 콘솔 (OS형 MVP)**입니다.  
외부 고객 포털이 아닌, 운영자가 직접 사용하는 내부 도구입니다.

### 핵심 운영 플로우
```
Place 수집/파싱 → 검수/보정 → 주문 입력 → 표준화
→ 실행 매핑 → 라우팅 → 템플릿 생성/전달
→ OrderItem 상태 추적 → 고객/실행처 정산 분리
```

---

## 현재 구현 범위 (Wave 1)

### ✅ 완료된 기능
1. **인증**: JWT 기반 로그인/로그아웃, 역할 기반 접근 (ADMIN / OPERATOR)
2. **Place 원본 스냅샷 저장**: Google Sheet / Excel 임포트 → `place_raw_snapshots` (불변)
3. **Place 검수 흐름**: 검수 상태 전이 (pending_review → confirmed/rejected), 검수 이력 기록
4. **주문 임포트**: Google Sheet URL → `order_raw_inputs` (불변 원본 저장)
5. **Order/OrderItem 표준화**: 1 row → N items 변환, 매핑 실패 시 `on_hold` 보존
6. **OrderItem 상태 추적**: 11개 상태 + 허용 전이 규칙 + 이력 기록
7. **수동 라우팅**: 실행처 배정 (`ready_to_route` → `assigned`)
8. **Offering 관리**: StandardProductType / SellableOffering / ProviderOffering / 매핑
9. **ImportJob 추적**: Google Sheet/Excel 임포트 작업 상태 관리 + 재시도
10. **AuditLog**: 전 도메인 액션 불변 기록
11. **대시보드**: 기본 집계 (Place/Order/OrderItem/ImportJob 상태별 카운트)

### ❌ Wave 1 미포함 (Wave 2+)
- 고객/실행처 정산 분리 (CustomerSettlement / ProviderSettlement)
- 자동 라우팅 엔진
- FormTemplate 생성/전달
- 전체 Google Sheet API (현재: CSV export 방식)
- 상세 RBAC (VIEWER 역할 등)

---

## API 엔드포인트 요약

Base: `http://localhost:8000/api/v1`  
Docs: `http://localhost:8000/docs` (DEBUG 모드)

| 그룹 | 경로 | 설명 |
|------|------|------|
| 인증 | `/auth/login`, `/auth/logout`, `/auth/me` | JWT 인증 |
| 사용자 | `/users` | ADMIN 전용 사용자 관리 |
| 플레이스 | `/places`, `/places/{id}/review`, `/places/{id}/snapshots` | Place 검수 흐름 |
| 임포트 | `/import-jobs/google-sheet`, `/import-jobs/excel`, `/import-jobs/{id}/retry` | 시트/Excel 임포트 |
| 주문 | `/orders`, `/orders/from-raw/{raw_id}` | Order 생성 및 raw 변환 |
| 주문아이템 | `/order-items`, `/order-items/{id}/status`, `/order-items/{id}/route` | 상태 추적/라우팅 |
| 실행처 | `/providers` | 매체사 등 실행처 관리 |
| 상품 | `/offerings/product-types`, `/offerings/sellable`, `/offerings/provider`, `/offerings/mappings` | Offering 관리 |
| 감사로그 | `/audit` | AuditLog 조회 |
| 대시보드 | `/dashboard` | 운영 현황 집계 |

---

## 데이터 아키텍처

### 핵심 테이블 (17개)
```
users                         — 운영자 계정 (ADMIN | OPERATOR)
agencies / brands             — 대행사/브랜드 (Wave 1: nullable FK)
places                        — 확정 플레이스 (소프트 삭제)
place_raw_snapshots           — 원본 파싱 결과 (INSERT 전용, 불변)
place_review_logs             — 검수 이력 (INSERT 전용, RESTRICT)
providers                     — 실행처 (매체사 등)
standard_product_types        — [초안] 표준 상품 유형 8개
sellable_offerings            — 판매 상품 (판매 구조 축)
provider_offerings            — 실행 상품 (실행 구조 축)
sellable_provider_mappings    — 1:N 연결
order_raw_inputs              — 원본 주문 행 (INSERT 전용, 불변)
orders                        — 주문 헤더
order_items                   — 주문 아이템 (상태 추적 단위)
order_item_status_histories   — 상태 이력 (INSERT 전용, RESTRICT)
import_jobs                   — 임포트 작업 추적
audit_logs                    — 전 도메인 감사 로그 (INSERT 전용)
```

### 설계 원칙
- **원본 불변**: `*_raw_*`, `*_logs`, `*_histories` 테이블은 INSERT 전용, CASCADE DELETE 금지
- **소프트 삭제**: `places`, `orders`, `order_items`에 `is_deleted` 적용
- **Loose Reference**: 일부 UUID 컬럼은 FK 없이 운영 (고아 레코드 허용, 문서화)
- **자동 추정 금지**: 매핑 실패 시 null 유지 (운영자 수동 확인)
- **판매/실행 분리**: SellableOffering ↔ ProviderOffering 구조적 분리

### OrderItem 상태 전이
```
received → on_hold → reviewing → ready_to_route → assigned → in_progress → done → confirmed → settlement_ready → closed
(모든 단계에서 → cancelled 가능)
```

---

## StandardProductType 초안 (확정 아님)

| 코드 | 표시명 | 채널 |
|------|--------|------|
| TRAFFIC | 트래픽 | naver_place |
| SAVE | 저장 | naver_place |
| AI_REAL | AI 실계정 | naver_place |
| AI_NONREAL | AI 비실계 | naver_place |
| BLOG_REPORTER | 기자단/실리뷰어 | blog |
| BLOG_DISPATCH | 블로그배포(최블/엔비블) | blog |
| XIAOHONGSHU | 샤오홍슈 | xiaohongshu |
| DIANPING | 따종디엔핑 | dianping |

---

## 개발 환경 실행

### 1. 사전 요구사항
- Docker & Docker Compose
- Python 3.12+

### 2. 환경 설정
```bash
cd backend
cp .env.example .env
# .env 파일에서 SECRET_KEY 등 수정
```

### 3. Docker로 실행 (권장)
```bash
docker-compose up -d postgres redis
cd backend
pip install -r requirements.txt
alembic upgrade head
python seed.py  # 시드 데이터 (개발용)
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 4. 전체 Docker
```bash
docker-compose up -d
```

### 5. 기본 계정 (시드 데이터)
- ADMIN: `admin@placeopt.internal` / `Admin1234!`
- OPERATOR: `operator@placeopt.internal` / `Oper1234!`

---

## 기술 스택
- **Backend**: FastAPI (Python 3.12) + SQLAlchemy 2.0 (async) + Alembic
- **DB**: PostgreSQL 16
- **Cache**: Redis 7
- **인증**: JWT (python-jose)
- **Google Sheet**: httpx CSV export (Wave 1) → google-auth Service Account (Wave 2)
- **Excel**: openpyxl

---

## 브랜치 전략
- `main`: 안정 버전
- `feat/wave1-foundation`: Wave 1 기반 (현재 작업)
- PR 범위: 기능 단위 (wave 단위 PR 권장)

---

## Wave 로드맵

| Wave | 주요 기능 |
|------|----------|
| Wave 1 | 스켈레톤, 인증, DB 스키마, Place/Order raw 저장, 검수, 표준화, 라우팅(수동) |
| Wave 2 | 정산(Customer/Provider), 자동 라우팅, 전체 Google Sheet API, VIEWER 역할 |
| Wave 3 | FormTemplate, 대시보드 고도화, 배치 재시도, 예외 처리 강화 |
| Wave 4+ | 자동화, 외부 포털, 분석 (MVP 이후) |

---

**Last Updated**: 2026-03-25  
**Status**: Wave 1 구현 완료 (GitHub 연동 대기)
