# PlaceOpt — 내부 운영 시스템 (Internal MVP)

## 프로젝트 개요

PlaceOpt는 네이버 플레이스 마케팅 운영팀을 위한 **내부 OS형 운영 도구**입니다.  
외부 고객용 SaaS가 아닌, 운영자가 직접 사용하는 내부 콘솔입니다.

**핵심 흐름**: Place 수집·파싱 → 검수 → 주문 접수 → 표준화 → 매핑·라우팅 → 템플릿 생성·전달 → OrderItem 상태 추적 → 정산

---

## Wave 1 완료 기능

### ✅ 인증 / 권한
- JWT 기반 로그인 (`POST /api/v1/auth/login`)
- 역할 체계: `ADMIN` | `OPERATOR` (Wave 1 확정. VIEWER 후속 추가 예정)
- 사용자 관리 CRUD (ADMIN 전용)

### ✅ Place 도메인
- Place CRUD (`/api/v1/places`)
- PlaceRawSnapshot INSERT 전용 저장 (`/api/v1/places/snapshots`)
- 검수 액션 (confirm / reject / note_added / field_edited)
- 검수 이력 조회

### ✅ Import 작업
- Google Sheet URL 기반 Import 작업 생성 (`POST /api/v1/import-jobs`) — **주 흐름**
- Excel 파일 업로드 보조 경로 (`POST /api/v1/import-jobs/upload`)
- Import Job 재시도 (`POST /api/v1/import-jobs/{id}/retry`)
- Raw Input 목록 조회

### ✅ Order / OrderItem
- `POST /api/v1/orders/from-raw`: raw_input → Order + OrderItem 1:1 표준화
- Order CRUD
- OrderItem 상태 전이 (`POST /api/v1/orders/{id}/items/{item_id}/status`)
- 상태 이력 조회
- 수동 실행처 배정 (`POST /api/v1/orders/{id}/items/{item_id}/assign-provider`)

### ✅ Provider / Product 구조
- Provider, StandardProductType, SellableOffering, ProviderOffering, Mapping CRUD
- Agency / Brand 테이블 (Wave 2 강제 예정, Wave 1은 nullable)

### ✅ 인프라
- Audit Log 조회
- Dashboard 요약 (`GET /api/v1/dashboard/summary`)
- Alembic 마이그레이션 (`001_initial_schema`)

---

## API 엔드포인트 목록

Base URL: `http://localhost:8000/api/v1`

| Method | Path | 설명 | 권한 |
|--------|------|------|------|
| POST | /auth/login | 로그인 | - |
| GET | /auth/me | 현재 사용자 | ANY |
| CRUD | /users | 사용자 관리 | ADMIN |
| GET/POST | /places | Place 목록/생성 | ANY/OP |
| PATCH/DELETE | /places/{id} | Place 수정/삭제 | OP |
| POST | /places/snapshots | 스냅샷 저장 | OP |
| POST | /places/{id}/review | 검수 액션 | OP |
| POST | /import-jobs | GSheet import 요청 | OP |
| POST | /import-jobs/upload | Excel 업로드 | OP |
| POST | /import-jobs/{id}/retry | 재시도 | OP |
| POST | /orders/from-raw | raw→OrderItem 표준화 | OP |
| GET/POST | /orders | 주문 목록/생성 | ANY/OP |
| PATCH/DELETE | /orders/{id} | 주문 수정/삭제 | OP |
| GET/PATCH | /orders/{id}/items/{item_id} | OrderItem 조회/수정 | ANY/OP |
| POST | /orders/{id}/items/{item_id}/status | 상태 전이 | OP |
| POST | /orders/{id}/items/{item_id}/assign-provider | 실행처 배정 | OP |
| CRUD | /providers | 실행처 관리 | ANY/OP |
| GET/POST | /standard-product-types | 표준 상품 유형 | ANY/ADMIN |
| CRUD | /sellable-offerings | 판매 상품 | ANY/OP |
| CRUD | /provider-offerings | 실행처 상품 | ANY/OP |
| CRUD | /mappings | SellableProvider 매핑 | ANY/OP |
| CRUD | /agencies, /brands | 대행사/브랜드 | ANY/OP |
| GET | /audit-logs | 감사 로그 | ANY |
| GET | /dashboard/summary | 운영 요약 | ANY |

---

## OrderItem 상태 흐름

```
received → on_hold ↔ reviewing → ready_to_route → assigned → in_progress → done → confirmed → settlement_ready → closed
                                                                                    ↑ (can also go back to in_progress)
cancelled (모든 단계에서 가능, closed 제외)
```

---

## StandardProductType 목록 (초안/제안안)

| 코드 | 표시명 | 시트 |
|------|--------|------|
| TRAFFIC | 리워드 트래픽 | 트래픽 취합 |
| SAVE | 리워드 저장하기 | 저장 취합 |
| AI_REAL | AI 실계정 프리미엄 배포 | AI(실계정) 취합 |
| AI_NONREAL | AI 비실계 프리미엄 배포 | AI(비실계) 취합 |
| BLOG_REPORTER | 실계정 기자단 | 기자단 취합 |
| BLOG_DISPATCH | 블로그 배포(최블/엔비블) | 최블엔비블 취합 |
| XIAOHONGSHU | 샤오홍슈 체험단 | 샤오홍슈 취합 |
| DIANPING | 따종디엔핑 등록 | 따종디엔핑 취합 |

---

## 기술 스택

- **Backend**: FastAPI (Python 3.12) + SQLAlchemy 2.0 (async) + Alembic
- **Database**: PostgreSQL 16 + Redis 7
- **Auth**: JWT (python-jose) + bcrypt (passlib)
- **Google Sheets**: gspread + google-auth
- **Container**: Docker + Docker Compose

---

## 로컬 실행

```bash
# 1. 환경변수 설정
cp backend/.env.example backend/.env
# .env 파일 편집

# 2. Docker Compose로 실행
docker-compose up -d

# 3. 마이그레이션 실행
docker-compose exec backend alembic upgrade head

# 4. API 문서 확인
open http://localhost:8000/docs
```

---

## 미구현 (Wave 2+ 예정)

- 실제 Google Sheet API 연동 (현재 pending 상태 생성만)
- FormTemplate 생성/전달
- CustomerSettlement / ProviderSettlement (정산 분리)
- 고급 라우팅 규칙 (RoutingRule 엔진)
- 키워드 전략 모듈
- 외부 고객 포털

---

## 저장소

- **GitHub**: https://github.com/lcm67088-tech/-03.25
- **Wave**: Wave 1 (skeleton + core domain + basic APIs)
- **마지막 업데이트**: 2026-03-25
