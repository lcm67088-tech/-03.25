# PlaceOpt 개발 기여 가이드

## 브랜치 전략

```
main          ← 배포 가능한 상태만 유지 (직접 push 금지)
├── feature/xxx   ← 기능 개발
├── fix/xxx       ← 버그 수정
└── chore/xxx     ← 설정·문서·리팩토링
```

### 브랜치 네이밍 규칙

| 유형 | 패턴 | 예시 |
|------|------|------|
| 기능 개발 | `feature/<scope>-<short-desc>` | `feature/frontend-form-template` |
| 버그 수정 | `fix/<scope>-<short-desc>` | `fix/frontend-order-status-badge` |
| 리팩토링 | `chore/<scope>-<short-desc>` | `chore/frontend-extract-hooks` |

### 개발 흐름

```bash
# 1. main 최신 상태로 시작
git checkout main && git pull origin main

# 2. feature 브랜치 생성
git checkout -b feature/frontend-form-template

# 3. 작업 → 커밋
git add .
git commit -m "feat(frontend): FormTemplate 목록 페이지 구현"

# 4. 타입체크 통과 확인 (커밋 전 권장)
cd frontend && pnpm run type-check

# 5. push
git push origin feature/frontend-form-template

# 6. GitHub에서 PR 생성 → main 방향
#    PR 제목: feat(frontend): FormTemplate 생성·전달 기능
#    PR 본문: 변경 내용, 스크린샷(선택), 테스트 방법
```

## 커밋 메시지 컨벤션

```
<type>(<scope>): <subject>

[optional body]
```

| type | 의미 |
|------|------|
| `feat` | 새 기능 |
| `fix` | 버그 수정 |
| `refactor` | 동작 변경 없는 코드 개선 |
| `chore` | 빌드·설정·문서 |
| `test` | 테스트 추가/수정 |

| scope | 의미 |
|-------|------|
| `frontend` | 프론트엔드 전반 |
| `backend` | 백엔드 전반 |
| `orders` | 주문 도메인 |
| `places` | Place 검수 도메인 |
| `settlement` | 정산 도메인 |
| `ci` | CI/CD 설정 |

### 예시

```
feat(frontend): OrderDetail 상태전이 버튼 추가
fix(backend): /orders 페이지네이션 total 계산 오류 수정
chore(ci): tsc type-check GitHub Actions 추가
```

## PR 머지 기준

- [ ] CI (typecheck + build) 통과
- [ ] 기능 동작 확인 (로컬 또는 샌드박스 스크린샷)
- [ ] 충돌 없음
- [ ] 리뷰어 승인 1명 이상 (본 프로젝트 현재: 생략 가능)

## 로컬 개발 셋업

```bash
git clone https://github.com/lcm67088-tech/-03.25
cd -03.25

# 백엔드 + 프론트 동시 실행
pm2 start ecosystem.config.cjs

# 프론트 개발 서버만
cd frontend && pnpm install && pnpm run dev

# 타입체크
cd frontend && pnpm run type-check

# 빌드 (빠른)
cd frontend && pnpm run build

# 빌드 (CI와 동일, 타입체크 포함)
cd frontend && pnpm run build:ci
```

## 환경별 실행 방법

| 환경 | 명령 | URL |
|------|------|-----|
| 개발 (HMR) | `pnpm run dev` | http://localhost:5173 |
| 빌드 미리보기 | `pnpm run build && pnpm run preview` | http://localhost:5173 |
| 운영 (Nginx) | `deploy/nginx.conf` 적용 후 dist/ 서빙 | https://your-domain.com |
