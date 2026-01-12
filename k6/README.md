# Open WebUI K6 성능 테스트 가이드

Open WebUI의 성능을 검증하기 위한 종합 테스트 도구입니다.

## 📋 목차
1. [빠른 시작](#-빠른-시작)
2. [테스트 타입별 가이드](#-테스트-타입별-가이드)  
3. [사용자 계정 테스트](#-사용자-계정-테스트)
4. [고급 설정](#️-고급-설정)
5. [결과 분석](#-결과-분석)
6. [문제 해결](#️-문제-해결)

---

## 🚀 빠른 시작

### 1. 설치 및 설정
```bash
# K6 설치
brew install k6  # macOS
sudo apt install k6  # Ubuntu

# 실행 권한 부여
chmod +x *.sh

# 서버 상태 확인
curl http://localhost:8088/health
```

### 2. 즉시 테스트 실행
```bash
# 가장 안전한 사용자 테스트 (추천)
./run-k6-tests.sh user

# 빠른 개발 테스트
./quick-test.sh

# 결과 분석
./simple-analyze.sh
```

---

## 🎯 테스트 타입별 가이드

### **📊 API 성능 테스트 스크립트**

| 스크립트 | 용도 | 실행시간 | 부하 수준 |
|---------|------|----------|-----------|
| **k6-api-load-test.js** | 종합 API 테스트 | 21-40분 | 높음 |
| **k6-user-load-test.js** | 사용자 안전 테스트 | 21분 | 낮음 |
| **k6-chat-message-test.js** | 실제 AI 대화 | 12분 | 매우 높음 |

### **🎮 테스트 타입**

#### **`user` - 일반 사용자 안전 테스트 (추천)**
```bash
./run-k6-tests.sh user
```
- ✅ **권한 오류 없음** - 관리자 API 제외
- ✅ **안전함** - 리소스 부담 낮음
- 🎯 **용도** - 일상 성능 모니터링

#### **`load` - 표준 부하 테스트**
```bash
./run-k6-tests.sh load
```
- 📊 **점진적 부하** - 30% → 60% → 100%
- ⏱️ **실행시간** - 약 26분
- ⚠️ **주의** - 일부 권한 오류 발생 가능

#### **`spike` - 급증 테스트**
```bash
./run-k6-tests.sh spike
```
- ⚡ **급격한 부하** - 갑작스런 트래픽 증가 시뮬레이션
- ⏱️ **실행시간** - 약 10분

#### **`stress` - 스트레스 테스트**
```bash
./run-k6-tests.sh stress
```
- 🔥 **고부하** - 시스템 한계점 찾기
- ⚠️ **주의** - 야간 실행 권장

#### **`chat` - 실제 AI 대화 테스트**
```bash
./run-k6-tests.sh chat
```
- 💬 **실제 AI 호출** - 리소스 집약적
- 🤖 **워크스페이스 기반** - 실제 사용 시나리오

---

## 🔒 사용자 계정 테스트

### **기본 실행**
```bash
# 기본 계정으로 안전 테스트
./run-k6-tests.sh user

# 커스텀 계정 사용
./run-k6-tests.sh user http://localhost:8088 user@company.com password123
```

### **환경변수 방식**
```bash
export BASE_URL="http://localhost:8088"
export EMAIL="test@mail.com"
export PASSWORD="1234"

./run-k6-tests.sh user
```

### **권한별 API 분류**

#### **✅ 일반 사용자 접근 가능**
| API | 기능 | 설명 |
|-----|------|------|
| `GET /api/v1/auths/` | 👤 본인 프로필 | 현재 사용자 정보 |
| `GET /api/v1/chats/` | 💬 채팅 목록 | 본인 채팅방 목록 |
| `GET /api/v1/models/` | 🤖 모델 목록 | 사용 가능한 AI 모델 |
| `GET /api/v1/prompts/` | 📝 프롬프트 | 접근 가능한 템플릿 |
| `GET /api/v1/documents/` | 📄 문서 목록 | 본인 업로드 문서 |
| `GET /api/v1/knowledge/` | 🧠 지식베이스 | 본인 지식베이스 |
| `GET /api/v1/tools/` | 🔧 도구 목록 | 사용 가능한 도구 |

#### **❌ 관리자 전용 (401 에러)**
- `GET /api/v1/users/` - 전체 사용자 목록
- `POST /api/v1/admin/*` - 관리자 설정
- `DELETE /api/v1/chats/all` - 전체 채팅 삭제

---

## ⚙️ 고급 설정

### **커스텀 실행**
```bash
# 동시 사용자와 시간 조정
./run-k6-tests.sh user http://localhost:8088 test@mail.com 1234 5 5m

# 환경변수로 세밀 제어
export VUS=20
export DURATION=15m
export TEST_FILE_UPLOAD=true
./run-k6-tests.sh load
```

### **AI 채팅 테스트 설정**
```bash
# 워크스페이스 기반 채팅
export WORKSPACE_ID="individual_mode"
export SEND_MESSAGES=true
export MESSAGE_DELAY=30
./run-k6-tests.sh chat
```

---

## 📝 스크립트별 상세 사용법

### **1. k6-api-load-test.js** - 통합 API 부하 테스트

**목적**: Open WebUI의 전체 API 엔드포인트 성능 테스트 (AI 채팅 제외)

#### 환경변수 (실행 파라미터)

| 환경변수 | 설명 | 기본값 | 예시 |
|---------|------|--------|------|
| `BASE_URL` | 타겟 서버 URL | `http://localhost:8088` | `http://api.example.com` |
| `EMAIL` | 로그인 이메일 (필수) | `test@mail.com` | `user@company.com` |
| `PASSWORD` | 로그인 비밀번호 (필수) | `1234` | `mypassword` |
| `VUS` | 가상 사용자 수 | `10` | `20` |
| `DURATION` | 테스트 지속 시간 | `10m` | `15m`, `30m` |
| `RPS` | 초당 요청 수 (설정시 VUS 무시) | `0` | `100` |
| `TEST_TYPE` | 테스트 타입 | `load` | `simple`, `spike`, `stress`, `volume` |
| `TEST_FILE_UPLOAD` | 파일 업로드 테스트 활성화 | `false` | `true` |
| `TEST_DOCUMENTS` | 문서/지식베이스 테스트 활성화 | `true` | `false` |
| `AUTH_TOKEN` | 사전 발급된 인증 토큰 | - | `eyJhbGc...` |

#### 사용 예시

```bash
# 기본 부하 테스트 (10명, 10분)
k6 run k6-api-load-test.js

# 20명 사용자로 15분간 테스트
k6 run --env VUS=20 --env DURATION=15m k6-api-load-test.js

# Spike 테스트 (급증 패턴)
k6 run --env TEST_TYPE=spike --env VUS=30 k6-api-load-test.js

# Stress 테스트 (한계점 찾기)
k6 run --env TEST_TYPE=stress k6-api-load-test.js

# 고정 부하 (Simple)
k6 run --env TEST_TYPE=simple --env VUS=15 --env DURATION=5m k6-api-load-test.js

# RPS 기반 테스트 (초당 100 요청)
k6 run --env RPS=100 --env DURATION=5m k6-api-load-test.js

# 파일 업로드 포함 테스트
k6 run --env TEST_FILE_UPLOAD=true --env VUS=5 k6-api-load-test.js

# 커스텀 서버 및 계정
k6 run --env BASE_URL=http://staging.example.com \
       --env EMAIL=test@example.com \
       --env PASSWORD=secretpass \
       --env VUS=10 \
       k6-api-load-test.js
```

#### 테스트되는 API 엔드포인트

- ✅ `POST /api/v1/auths/signin` - 인증
- ✅ `GET /api/v1/auths/` - 현재 사용자 정보
- ✅ `GET /api/v1/users/` - 사용자 목록 (관리자 전용, 401/403 허용)
- ✅ `GET /api/v1/chats/` - 채팅 목록
- ✅ `GET /api/models` - 모델 목록 (메인)
- ✅ `GET /api/v1/models/` - 모델 목록 (보조)
- ✅ `GET /api/v1/prompts/` - 프롬프트 목록
- ✅ `GET /api/v1/documents/` - 문서 목록
- ✅ `GET /api/v1/knowledge/` - 지식베이스 목록
- ✅ `GET /api/v1/tools/` - 도구 목록
- ✅ `POST /api/v1/files/` - 파일 업로드 (옵션)

---

### **2. k6-user-load-test.js** - 일반 사용자 안전 테스트

**목적**: 관리자 권한 없이 일반 사용자가 접근 가능한 API만 테스트 (권한 오류 없음)

#### 환경변수 (실행 파라미터)

| 환경변수 | 설명 | 기본값 | 예시 |
|---------|------|--------|------|
| `BASE_URL` | 타겟 서버 URL | `http://localhost:8088` | `http://api.example.com` |
| `EMAIL` | 로그인 이메일 | `test@mail.com` | `user@company.com` |
| `PASSWORD` | 로그인 비밀번호 | `1234` | `mypassword` |
| `VUS` | 가상 사용자 수 | `10` | `20` |
| `DURATION` | 테스트 지속 시간 | `10m` | `15m`, `30m` |
| `RPS` | 초당 요청 수 (설정시 VUS 무시) | `0` | `50` |
| `TEST_TYPE` | 테스트 타입 | `load` | `simple`, `spike`, `stress`, `volume` |
| `TEST_FILE_UPLOAD` | 파일 업로드 테스트 활성화 | `false` | `true` |
| `AUTH_TOKEN` | 사전 발급된 인증 토큰 | - | `eyJhbGc...` |

#### 사용 예시

```bash
# 기본 사용자 안전 테스트
k6 run k6-user-load-test.js

# 5명 사용자로 가볍게 테스트
k6 run --env VUS=5 --env DURATION=5m k6-user-load-test.js

# Spike 테스트 (사용자 권한)
k6 run --env TEST_TYPE=spike --env VUS=20 k6-user-load-test.js

# 고정 부하 테스트
k6 run --env TEST_TYPE=simple --env VUS=10 --env DURATION=10m k6-user-load-test.js

# 파일 업로드 포함 (사용자 파일만)
k6 run --env TEST_FILE_UPLOAD=true --env VUS=5 k6-user-load-test.js

# Volume 테스트 (장기 안정성)
k6 run --env TEST_TYPE=volume --env VUS=15 k6-user-load-test.js
```

#### 테스트되는 API 엔드포인트

- ✅ `POST /api/v1/auths/signin` - 인증
- ✅ `GET /api/v1/auths/` - 현재 사용자 정보 (본인만)
- ✅ `GET /api/v1/chats/` - 채팅 목록 (본인 채팅만)
- ✅ `GET /api/models` - 모델 목록
- ✅ `GET /api/v1/prompts/` - 프롬프트 목록 (접근 가능한 것만)
- ✅ `GET /api/v1/documents/` - 문서 목록 (본인 문서만)
- ✅ `GET /api/v1/knowledge/` - 지식베이스 (본인 것만)
- ✅ `GET /api/v1/tools/` - 도구 목록 (사용 가능한 것만)
- ✅ `POST /api/v1/files/` - 파일 업로드 (옵션, 본인 파일)

#### ❌ 제외된 API (관리자 전용)
- `GET /api/v1/users/` - 전체 사용자 목록 (401/403)
- 모든 관리자 API

---

### **3. k6-chat-message-test.js** - 실제 AI 채팅 테스트

**목적**: 워크스페이스 환경에서 실제 AI 모델과 대화하며 성능 테스트 (리소스 집약적)

#### 환경변수 (실행 파라미터)

| 환경변수 | 설명 | 기본값 | 예시 |
|---------|------|--------|------|
| `BASE_URL` | 타겟 서버 URL | `http://localhost:8088` | `http://api.example.com` |
| `TEST_EMAIL` | 기존 사용자 이메일 (필수) | `test@mail.com` | `user@company.com` |
| `TEST_PASSWORD` | 기존 사용자 비밀번호 (필수) | `1234` | `mypassword` |
| `WORKSPACE_ID` | 워크스페이스 ID | `individual_mode` | `team_workspace_123` |
| `SEND_MESSAGES` | 실제 메시지 전송 활성화 | `true` | `false` |
| `MESSAGE_DELAY` | 메시지 간 대기 시간 (초) | `30` | `10`, `60` |
| `USE_WORKSPACE_MODELS` | 워크스페이스 모델 사용 | `true` | `false` |
| `VUS` | 가상 사용자 수 | `5` | `10` |
| `DURATION` | 테스트 지속 시간 | `12m` | `15m`, `20m` |
| `TEST_TYPE` | 테스트 타입 | `load` | `simple`, `spike`, `stress`, `volume` |

#### 사용 예시

```bash
# 기본 채팅 테스트 (5명, 12분)
k6 run k6-chat-message-test.js

# 실제 AI 메시지 전송 활성화
k6 run --env SEND_MESSAGES=true k6-chat-message-test.js

# 10명 사용자로 20분간 테스트
k6 run --env VUS=10 --env DURATION=20m k6-chat-message-test.js

# 특정 워크스페이스로 테스트
k6 run --env WORKSPACE_ID=team_workspace_123 \
       --env TEST_EMAIL=team@example.com \
       k6-chat-message-test.js

# 고정 부하 (Simple) - AI 부하 테스트
k6 run --env TEST_TYPE=simple --env VUS=3 --env DURATION=10m k6-chat-message-test.js

# Stress 테스트 (AI 한계점 찾기)
k6 run --env TEST_TYPE=stress k6-chat-message-test.js

# 메시지 대기 시간 단축 (빠른 테스트)
k6 run --env MESSAGE_DELAY=10 --env VUS=3 k6-chat-message-test.js

# 메시지 전송 없이 채팅방 생성만 테스트
k6 run --env SEND_MESSAGES=false k6-chat-message-test.js

# Volume 테스트 (AI 장기 안정성)
k6 run --env TEST_TYPE=volume --env VUS=8 k6-chat-message-test.js
```

#### 테스트 시나리오

- **30%**: 채팅 목록만 조회 (가벼운 작업)
- **70%**: 실제 AI 대화 (채팅방 생성 + 메시지 전송)

#### 테스트되는 API 엔드포인트

- ✅ `POST /api/v1/auths/signin` - 인증
- ✅ `GET /api/v1/workspaces/` - 워크스페이스 목록
- ✅ `GET /api/v1/models/?workspace={id}` - 워크스페이스 모델
- ✅ `GET /api/v1/prompts/?workspace={id}` - 워크스페이스 프롬프트
- ✅ `POST /api/v1/chats/new` - 채팅방 생성
- ✅ `POST /api/chat/completions` - AI 메시지 전송 (OpenAI 호환)
- ✅ `GET /api/v1/chats/{id}` - 채팅 히스토리 조회
- ✅ `GET /api/v1/chats/` - 채팅 목록

#### ⚠️ 주의사항

- **리소스 집약적**: AI 모델 호출로 인해 CPU/GPU/메모리 사용량이 높음
- **응답 시간**: AI 응답은 일반 API보다 느림 (threshold: p95 < 5000ms)
- **동시 사용자 제한**: 기본 5명으로 보수적 설정 (서버 사양에 따라 조정)
- **야간 테스트 권장**: Stress 테스트는 리소스 부하가 크므로 운영 시간 피하기

---

## 🎯 테스트 타입별 상세 설명

### **`load` - 표준 부하 테스트 (기본값)**

점진적으로 부하를 증가시켜 시스템의 안정성 검증

#### 부하 패턴
```
30% 사용자 → (유지) → 60% 사용자 → (유지) → 100% 사용자 → (유지) → 종료
```

#### 적합한 상황
- 배포 전 일반적인 성능 검증
- 점진적 트래픽 증가 대응 확인
- 정기적인 성능 모니터링

#### 실행 예시
```bash
k6 run --env TEST_TYPE=load --env VUS=20 k6-api-load-test.js
k6 run --env TEST_TYPE=load --env VUS=10 k6-user-load-test.js
k6 run --env TEST_TYPE=load --env VUS=5 k6-chat-message-test.js
```

---

### **`simple` - 고정 부하 테스트**

일정한 사용자 수를 유지하며 안정성 검증

#### 부하 패턴
```
VUS 사용자 고정 → (DURATION 동안 유지) → 종료
```

#### 적합한 상황
- 특정 부하에서의 안정성 검증
- 리소스 사용량 일정 모니터링
- 빠른 개발 중 테스트

#### 실행 예시
```bash
# 10명 고정으로 5분간 테스트
k6 run --env TEST_TYPE=simple --env VUS=10 --env DURATION=5m k6-api-load-test.js

# 3명 고정으로 AI 채팅 테스트
k6 run --env TEST_TYPE=simple --env VUS=3 --env DURATION=10m k6-chat-message-test.js
```

---

### **`spike` - 급증 테스트**

갑작스런 트래픽 증가에 대한 대응 능력 검증

#### 부하 패턴
```
30% 사용자 → (급증) → 200% 사용자 → (유지) → 30% 사용자 → (회복)
```

#### 적합한 상황
- 이벤트/프로모션 트래픽 대비
- 오토스케일링 검증
- 갑작스런 부하 대응 테스트

#### 실행 예시
```bash
k6 run --env TEST_TYPE=spike --env VUS=30 k6-api-load-test.js
k6 run --env TEST_TYPE=spike --env VUS=20 k6-user-load-test.js
k6 run --env TEST_TYPE=spike --env VUS=10 k6-chat-message-test.js
```

---

### **`stress` - 스트레스 테스트**

시스템의 한계점을 찾기 위한 고부하 테스트

#### 부하 패턴
```
k6-api-load-test.js:    50 → 100 → 300 → 500 → 1000 → (10분 유지)
k6-user-load-test.js:   20 → 50  → 100 → 200 → 300  → (10분 유지)
k6-chat-message-test.js: 5 → 10  → 20  → 30  → (10분 유지)
```

#### 적합한 상황
- 시스템 한계점 파악
- 병목 지점 식별
- 용량 계획 (Capacity Planning)

#### 실행 예시
```bash
# ⚠️ 야간 실행 권장
k6 run --env TEST_TYPE=stress k6-api-load-test.js
k6 run --env TEST_TYPE=stress k6-user-load-test.js
k6 run --env TEST_TYPE=stress k6-chat-message-test.js
```

---

### **`volume` - 볼륨 테스트 (장기 안정성)**

장시간 지속적인 부하로 메모리 누수, 안정성 검증

#### 부하 패턴
```
k6-api-load-test.js:    VUS * 150% → (30분 유지)
k6-user-load-test.js:   VUS * 120% → (30분 유지)
k6-chat-message-test.js: VUS * 80%  → (30분 유지)
```

#### 적합한 상황
- 메모리 누수 탐지
- 장시간 운영 안정성 검증
- 리소스 사용 패턴 분석

#### 실행 예시
```bash
# ⚠️ 30분 이상 소요
k6 run --env TEST_TYPE=volume --env VUS=10 k6-api-load-test.js
k6 run --env TEST_TYPE=volume --env VUS=10 k6-user-load-test.js
k6 run --env TEST_TYPE=volume --env VUS=5 k6-chat-message-test.js
```

---

## 📊 테스트 타입별 비교표

| 테스트 타입 | 실행 시간 | 부하 수준 | 목적 | 권장 VUS |
|-----------|----------|----------|------|----------|
| **simple** | DURATION | 고정 | 빠른 검증 | 5-15 |
| **load** | 26분 | 점진적 증가 | 일반 성능 검증 | 10-30 |
| **spike** | 10분 | 급증/급감 | 이벤트 대비 | 20-50 |
| **stress** | 27분 | 매우 높음 | 한계점 탐색 | 자동 증가 |
| **volume** | 40분+ | 장시간 유지 | 안정성 검증 | 10-20 |

---

## 💡 권장 조합

### **일상 모니터링**
```bash
k6 run --env TEST_TYPE=simple --env VUS=5 --env DURATION=3m k6-user-load-test.js
```

### **배포 전 검증**
```bash
# 1단계: 안전 테스트
k6 run --env TEST_TYPE=load --env VUS=10 k6-user-load-test.js

# 2단계: 통합 API 테스트
k6 run --env TEST_TYPE=load --env VUS=15 k6-api-load-test.js

# 3단계: AI 기능 테스트
k6 run --env TEST_TYPE=simple --env VUS=3 k6-chat-message-test.js
```

### **성능 한계 파악**
```bash
# ⚠️ 야간 실행 권장
k6 run --env TEST_TYPE=stress k6-api-load-test.js
k6 run --env TEST_TYPE=stress k6-chat-message-test.js
```

---

### **직접 K6 실행 (래퍼 스크립트 없이)**
```bash
# API 부하 테스트
k6 run --env TEST_TYPE=load --env VUS=10 k6-api-load-test.js

# 사용자 안전 테스트
k6 run --env VUS=5 --env DURATION=5m k6-user-load-test.js

# AI 채팅 테스트
k6 run --env SEND_MESSAGES=true k6-chat-message-test.js
```

---

## 📊 결과 분석

### **분석 스크립트 사용**
```bash
# 자동으로 최신 결과 분석
./simple-analyze.sh

# 특정 파일 분석
./simple-analyze.sh results/k6-user-result-20250905-143000.json
```

### **분석 결과 해석**

#### **✅ 좋은 성능**
```
✅ 95% 응답시간이 우수합니다 (< 500ms)
✅ 에러율이 우수합니다 (< 1%)
✅ 부하 증가에도 안정적인 응답시간 유지
```

#### **⚠️ 주의 필요**
```
⚠️ 95% 응답시간이 양호합니다 (< 1000ms)  
⚠️ 에러율이 양호합니다 (< 5%)
📊 부하 증가시 응답시간이 다소 증가 - 모니터링 필요
```

#### **❌ 개선 필요**
```
❌ 95% 응답시간이 개선이 필요합니다 (> 1000ms)
❌ 에러율이 높습니다 (> 5%)
⚠️ 부하 증가시 응답시간이 크게 증가함 - 스케일링 필요
```

### **성능 기준**
- **응답시간**: 95% < 500ms (우수), < 1000ms (양호)
- **에러율**: < 1% (우수), < 5% (양호)
- **부하 증가**: 4배 이하 (안정), 4배 초과 (스케일링 필요)

---

## 🎯 추천 시나리오

### **일상 모니터링**
```bash
# 매일 - 빠른 확인
./run-k6-tests.sh user
./simple-analyze.sh

# 주간 - 부하 테스트
./run-k6-tests.sh load
```

### **배포 전 검증**
```bash
# 1단계: 안전 테스트
./run-k6-tests.sh user

# 2단계: 부하 테스트 (에러 허용)
./run-k6-tests.sh load  

# 3단계: AI 기능 테스트
./run-k6-tests.sh chat

# 분석
./simple-analyze.sh
```

### **성능 튜닝**
```bash
# 현재 성능 측정
./run-k6-tests.sh user
./simple-analyze.sh > before.txt

# 설정 변경 후...

# 개선 후 측정
./run-k6-tests.sh user
./simple-analyze.sh > after.txt

# 비교
diff before.txt after.txt
```

---

## 🛠️ 문제 해결

### **1. 로그인 실패**
```bash
# 증상: Authentication failed, skipping tests

# 해결책:
# 1) 서버 상태 확인
curl http://localhost:8088/health

# 2) 로그인 테스트
curl -X POST http://localhost:8088/api/v1/auths/signin \
  -H "Content-Type: application/json" \
  -d '{"email":"test@mail.com","password":"1234"}'

# 3) 올바른 계정 사용
./run-k6-tests.sh user http://localhost:8088 올바른이메일 올바른비밀번호
```

### **2. 높은 에러율 (401 Unauthorized)**
```bash
# 증상: ❌ 에러율이 높습니다 (> 5%)

# 원인: 관리자 전용 API 호출 시도

# 해결: user 테스트 사용
./run-k6-tests.sh user  # 권한 오류 없음
```

### **3. 서버 과부하**
```bash
# 증상: ⚠️ 부하 증가시 응답시간이 크게 증가함

# 해결:
# 1) 동시 사용자 수 줄이기
./run-k6-tests.sh user http://localhost:8088 test@mail.com 1234 3 5m

# 2) 테스트 간격 늘리기  
sleep 60 && ./run-k6-tests.sh user

# 3) 서버 리소스 확인
htop  # CPU/메모리 사용률
```

### **4. AI 채팅 테스트 실패**
```bash
# 증상: ERROR: WORKSPACE_ID is required

# 해결:
export WORKSPACE_ID="individual_mode"
./run-k6-tests.sh chat

# 또는 직접 지정
./run-k6-tests.sh chat http://localhost:8088 test@mail.com 1234 3 5m workspace_id
```

---

## 📁 파일 구조

```
k6/
├── README.md                          # 이 가이드
├── run-k6-tests.sh                   # 통합 실행 스크립트
├── quick-test.sh                     # 빠른 개발 테스트
├── simple-analyze.sh                 # 결과 분석 도구
├── cleanup-test-data.sh              # 데이터베이스 전용 정리 도구
├── k6-api-load-test.js              # 통합 API 부하 테스트
├── k6-user-load-test.js             # 사용자 안전 테스트  
├── k6-chat-message-test.js          # AI 채팅 테스트
└── results/                          # 테스트 결과 저장 (영구 보존)
    ├── k6-*-result-*.json           # 상세 JSON 결과
    └── k6-*-summary-*.txt           # 요약 결과
```

---

## 📚 참고 명령어

```bash
# 결과 관리
ls -la results/                      # 결과 파일 목록 (영구 보존됨)
./cleanup-test-data.sh               # 데이터베이스 테스트 데이터만 정리

# 분석
./simple-analyze.sh | head -50      # 요약만 보기
./simple-analyze.sh | grep "API"    # API 분석만 보기

# 서버 모니터링
curl -s http://localhost:8088/health # 서버 상태
tail -f /var/log/openwebui.log      # 실시간 로그
```

---

## 💡 간소화된 워크플로우

### **📋 기본 3단계 프로세스**
```bash
1. 테스트 실행 → ./run-k6-tests.sh [타입]
2. 결과 확인 → ./simple-analyze.sh
3. 데이터 정리 → ./cleanup-test-data.sh
```

### **🎯 테스트 타입별 가이드**
| 용도 | 명령어 | 소요시간 | 동시사용자 | 듀레이션 설정 |
|------|---------|----------|------------|---------------|
| **개발 중** | `./quick-test.sh` | 30초 | 2명 | 30초 |
| **일상 점검** | `./run-k6-tests.sh user` | 21분 | 10명 | 10분 (기본값) |
| **배포 전** | `./run-k6-tests.sh load` | 26분 | 단계적 증가 | 26분 (단계별) |
| **AI 기능** | `./run-k6-tests.sh chat` | 12분 | 5명 | 12분 (단계별) |

### **⚙️ 듀레이션 커스터마이징**
```bash
# 기본 사용법: [타입] [URL] [이메일] [비밀번호] [동시사용자] [지속시간]
./run-k6-tests.sh user http://localhost:8088 test@mail.com 1234 5 3m

# 예시: 5명 사용자로 3분간 테스트
./run-k6-tests.sh user http://localhost:8088 test@mail.com 1234 5 3m

# 예시: 20명 사용자로 15분간 부하 테스트
./run-k6-tests.sh load http://localhost:8088 test@mail.com 1234 20 15m
```

### **✨ 권장 실행 순서**
```bash
# 1. 테스트 실행 (기본값: 10명, 10분)
./run-k6-tests.sh user

# 또는 커스텀 설정 (5명, 5분)
./run-k6-tests.sh user http://localhost:8088 test@mail.com 1234 5 5m

# 2. 결과 분석
./simple-analyze.sh

# 3. 데이터베이스 정리 (필요시)
./cleanup-test-data.sh
```

### **⏱️ 듀레이션 포맷**
- `30s` = 30초
- `5m` = 5분
- `1h` = 1시간
- `90s` = 1분 30초
