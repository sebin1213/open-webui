#!/bin/bash

# Open WebUI K6 부하 테스트 실행 스크립트
# 사용법: ./run-k6-tests.sh [테스트타입] [베이스URL] [이메일] [패스워드] [동시사용자수] [지속시간] [워크스페이스ID]
# 테스트타입: load, spike, stress, volume, simple, user, chat
# 예시: ./run-k6-tests.sh load http://localhost:8088 user@company.com password123 20 5m
# 채팅 예시: ./run-k6-tests.sh chat http://localhost:8088 user@company.com password123 5 10m workspace-123

set -e

# 기본 설정값
DEFAULT_TEST_TYPE="load"
DEFAULT_BASE_URL="http://localhost:8088"
DEFAULT_EMAIL="test@mail.com"
DEFAULT_PASSWORD="1234"
DEFAULT_VUS="10"
DEFAULT_DURATION="10m"
DEFAULT_WORKSPACE_ID="test_workspace"

# 인자 처리
TEST_TYPE=${1:-$DEFAULT_TEST_TYPE}
BASE_URL=${2:-$DEFAULT_BASE_URL}
TEST_EMAIL=${3:-$DEFAULT_EMAIL}    # 기본값 사용 가능
TEST_PASSWORD=${4:-$DEFAULT_PASSWORD}  # 기본값 사용 가능
CUSTOM_VUS=${5:-$DEFAULT_VUS}
CUSTOM_DURATION=${6:-$DEFAULT_DURATION}
WORKSPACE_ID=${7:-$DEFAULT_WORKSPACE_ID}  # 워크스페이스 ID 추가 (chat 테스트용)

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 로고 출력
echo -e "${BLUE}"
echo "=================================================="
echo "     Open WebUI K6 부하 테스트 실행기"
echo "=================================================="
echo -e "${NC}"

# k6 설치 확인
if ! command -v k6 &> /dev/null; then
    echo -e "${RED}❌ k6이 설치되지 않았습니다.${NC}"
    echo -e "${YELLOW}macOS: brew install k6${NC}"
    echo -e "${YELLOW}Ubuntu: sudo apt install k6${NC}"
    echo -e "${YELLOW}기타: https://k6.io/docs/getting-started/installation/${NC}"
    exit 1
fi

echo -e "${GREEN}✅ k6 설치 확인됨${NC}"

# 서버 상태 확인
echo -e "${BLUE}🔍 서버 상태 확인 중: $BASE_URL${NC}"
if curl -s --max-time 10 "$BASE_URL/health" > /dev/null 2>&1; then
    echo -e "${GREEN}✅ 서버가 정상적으로 응답합니다${NC}"
else
    echo -e "${RED}❌ 서버에 연결할 수 없습니다: $BASE_URL${NC}"
    echo -e "${YELLOW}💡 서버가 실행 중인지 확인하고 URL을 다시 확인하세요${NC}"
    exit 1
fi

# 테스트 파일 존재 확인 - 테스트 타입에 따른 스크립트 선택
case $TEST_TYPE in
    "chat")
        TEST_FILE="k6-chat-message-test.js"
        ;;
    "user")
        # 일반 사용자 전용 안전한 API 테스트
        TEST_FILE="k6-user-load-test.js"
        ;;
    *)
        # load, spike, stress, volume, simple - 통합 API 테스트 (관리자 권한 포함 가능)
        TEST_FILE="k6-api-load-test.js"
        ;;
esac

if [ ! -f "$TEST_FILE" ]; then
    echo -e "${RED}❌ 테스트 파일을 찾을 수 없습니다: $TEST_FILE${NC}"
    echo -e "${YELLOW}사용 가능한 테스트 타입: load, spike, stress, volume, simple, user, chat${NC}"
    exit 1
fi

# 테스트 설정 출력
echo -e "${BLUE}"
echo "=================================================="
echo "              테스트 설정 정보"
echo "=================================================="
echo -e "${NC}"
echo -e "${YELLOW}테스트 타입:${NC} $TEST_TYPE"
echo -e "${YELLOW}대상 URL:${NC} $BASE_URL"
echo -e "${YELLOW}사용자 이메일:${NC} $TEST_EMAIL (기존 계정)"
echo -e "${YELLOW}동시 사용자:${NC} $CUSTOM_VUS명"
echo -e "${YELLOW}지속 시간:${NC} $CUSTOM_DURATION"
if [ "$TEST_TYPE" = "chat" ] && [ -n "$WORKSPACE_ID" ]; then
    echo -e "${YELLOW}워크스페이스 ID:${NC} $WORKSPACE_ID"
fi
echo -e "${YELLOW}테스트 파일:${NC} $TEST_FILE"
echo ""

# 테스트 타입별 설명
case $TEST_TYPE in
    "load")
        echo -e "${GREEN}📈 부하 테스트${NC}: 예상 사용자 수에서 시스템 성능 검증"
        echo -e "${BLUE}   - 최대 동시 사용자: 30명"
        echo -e "${BLUE}   - 테스트 시간: 약 21분"
        echo -e "${BLUE}   - 목표: 정상 운영 환경 시뮬레이션${NC}"
        ;;
    "spike")
        echo -e "${YELLOW}⚡ 스파이크 테스트${NC}: 갑작스러운 트래픽 증가 상황 테스트"
        echo -e "${BLUE}   - 최대 동시 사용자: 100명"
        echo -e "${BLUE}   - 테스트 시간: 약 10분"
        echo -e "${BLUE}   - 목표: 급격한 트래픽 변화 대응 능력 검증${NC}"
        ;;
    "stress")
        echo -e "${RED}🔥 스트레스 테스트${NC}: 시스템 한계점 찾기"
        echo -e "${BLUE}   - 단계별 부하: 50→100→300→500→1000명"
        echo -e "${BLUE}   - 테스트 시간: 약 27분"
        echo -e "${BLUE}   - 목표: 고부하 상황에서 시스템 한계점 확인${NC}"
        ;;
    "volume")
        echo -e "${BLUE}⏳ 볼륨 테스트${NC}: 장시간 지속적인 부하 테스트"
        echo -e "${BLUE}   - 최대 동시 사용자: 50명"
        echo -e "${BLUE}   - 테스트 시간: 약 40분"
        echo -e "${BLUE}   - 목표: 메모리 누수, 성능 저하 등 장기 운영 이슈 발견${NC}"
        ;;
    "simple")
        echo -e "${GREEN}⚡ 간단 테스트${NC}: 상수 부하로 빠른 성능 확인"
        echo -e "${BLUE}   - 동시 사용자: 설정값 고정 (기본 10명)"
        echo -e "${BLUE}   - 테스트 시간: 설정값 고정 (기본 10분)"
        echo -e "${BLUE}   - 목표: 빠른 성능 베이스라인 측정${NC}"
        ;;
    "chat")
        echo -e "${GREEN}💬 워크스페이스 채팅 테스트${NC}: 워크스페이스 환경에서 AI 대화"
        echo -e "${BLUE}   - 최대 동시 사용자: 5명 (AI 처리 고려)"
        echo -e "${BLUE}   - 테스트 시간: 약 12분"
        echo -e "${BLUE}   - 목표: 워크스페이스 모델(기본/pipe function)을 통한 AI 대화 성능 측정${NC}"
        echo -e "${RED}   ⚠️  주의: 실제 AI 모델을 사용하므로 높은 리소스 소모${NC}"
        ;;
    "user")
        echo -e "${GREEN}👤 사용자 테스트${NC}: 일반 사용자 권한으로만 안전한 API 테스트"
        echo -e "${BLUE}   - 최대 동시 사용자: 10명 (관리자 권한 불필요)"
        echo -e "${BLUE}   - 테스트 시간: 약 21분"
        echo -e "${BLUE}   - 목표: 관리자 권한이 없는 일반 사용자 환경 시뮬레이션${NC}"
        ;;
    *)
        echo -e "${RED}❌ 지원하지 않는 테스트 타입: $TEST_TYPE${NC}"
        echo -e "${YELLOW}사용 가능한 테스트 타입: load, spike, stress, volume, simple, user, chat${NC}"
        exit 1
        ;;
esac

echo ""
echo -e "${YELLOW}⚠️  주의사항:${NC}"
echo -e "${YELLOW}   - 테스트 중에는 서버에 높은 부하가 발생합니다${NC}"
echo -e "${YELLOW}   - 운영 환경에서는 신중히 실행하세요${NC}"
echo -e "${YELLOW}   - 테스트 결과는 results/ 폴더에 저장됩니다${NC}"
echo ""

# 사용자 확인
read -p "테스트를 시작하시겠습니까? (y/N): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${YELLOW}테스트가 취소되었습니다${NC}"
    exit 0
fi

echo -e "${GREEN}🚀 테스트 시작...${NC}"
echo ""

# 결과 저장 디렉토리 생성
RESULTS_DIR="results"
mkdir -p "$RESULTS_DIR"

# 결과 파일 이름 생성
TIMESTAMP=$(date +"%Y%m%d-%H%M%S")
RESULT_FILE="$RESULTS_DIR/k6-${TEST_TYPE}-result-${TIMESTAMP}.json"   # JSONL (raw samples)
SUMMARY_JSON="$RESULTS_DIR/k6-${TEST_TYPE}-summary-${TIMESTAMP}.json" # Aggregated summary JSON
SUMMARY_FILE="$RESULTS_DIR/k6-${TEST_TYPE}-summary-${TIMESTAMP}.txt"  # Human-readable summary

# k6 테스트 실행
# 계정 정보 확인 및 안내
if [ "$TEST_EMAIL" = "$DEFAULT_EMAIL" ] && [ "$TEST_PASSWORD" = "$DEFAULT_PASSWORD" ]; then
    echo -e "${YELLOW}💡 기본 테스트 계정을 사용합니다: $TEST_EMAIL${NC}"
    echo -e "${BLUE}   실제 계정을 사용하려면: ./run-k6-tests.sh $TEST_TYPE $BASE_URL your@email.com yourpassword${NC}"
    echo ""
fi

# 계정 정보 검증 (빈 값 확인)
if [ -z "$TEST_EMAIL" ] || [ -z "$TEST_PASSWORD" ]; then
    echo -e "${RED}❌ 사용자 이메일과 패스워드가 필요합니다${NC}"
    echo -e "${YELLOW}사용법: ./run-k6-tests.sh $TEST_TYPE $BASE_URL user@company.com password123${NC}"
    exit 1
fi

# Chat 테스트의 경우 워크스페이스 ID 설정 (기본값 사용 가능)
if [ "$TEST_TYPE" = "chat" ] && [ -z "$WORKSPACE_ID" ]; then
    WORKSPACE_ID="test_workspace"
    echo -e "${YELLOW}💡 워크스페이스 ID가 지정되지 않아 기본값 사용: $WORKSPACE_ID${NC}"
fi

if [ "$TEST_FILE" = "k6-api-load-test.js" ]; then
    # API 통합 스크립트는 테스트 타입을 환경변수로 전달
    k6 run \
        --out json="$RESULT_FILE" \
        --summary-export "$SUMMARY_JSON" \
        -e BASE_URL="$BASE_URL" \
        -e EMAIL="$TEST_EMAIL" \
        -e PASSWORD="$TEST_PASSWORD" \
        -e TEST_TYPE="$TEST_TYPE" \
        -e VUS="$CUSTOM_VUS" \
        -e DURATION="$CUSTOM_DURATION" \
        -e TEST_FILE_UPLOAD="false" \
        -e TEST_DOCUMENTS="true" \
        "$TEST_FILE"
elif [ "$TEST_FILE" = "k6-chat-message-test.js" ]; then
    # 채팅 스크립트는 워크스페이스 ID 포함
    k6 run \
        --out json="$RESULT_FILE" \
        --summary-export "$SUMMARY_JSON" \
        -e BASE_URL="$BASE_URL" \
        -e TEST_EMAIL="$TEST_EMAIL" \
        -e TEST_PASSWORD="$TEST_PASSWORD" \
        -e WORKSPACE_ID="$WORKSPACE_ID" \
        -e SEND_MESSAGES="true" \
        -e MESSAGE_DELAY="30" \
        -e USE_WORKSPACE_MODELS="true" \
        -e VUS="$CUSTOM_VUS" \
        -e DURATION="$CUSTOM_DURATION" \
        -e TEST_TYPE="$TEST_TYPE" \
        "$TEST_FILE"
else
    # 기타 스크립트는 기본 실행 (user-load-test.js 등)
    k6 run \
        --out json="$RESULT_FILE" \
        --summary-export "$SUMMARY_JSON" \
        -e BASE_URL="$BASE_URL" \
        -e EMAIL="$TEST_EMAIL" \
        -e PASSWORD="$TEST_PASSWORD" \
        -e VUS="$CUSTOM_VUS" \
        -e DURATION="$CUSTOM_DURATION" \
        -e TEST_TYPE="$TEST_TYPE" \
        "$TEST_FILE"
fi

# 테스트 완료 메시지
echo ""
echo -e "${GREEN}"
echo "=================================================="
echo "              테스트 완료!"
echo "=================================================="
echo -e "${NC}"
echo -e "${GREEN}✅ 테스트가 성공적으로 완료되었습니다${NC}"
echo -e "${YELLOW}📊 결과 파일:${NC} $RESULT_FILE"
echo ""

# 결과 요약 생성 및 표시
if command -v jq &> /dev/null; then
    if [ -f "$SUMMARY_JSON" ]; then
        # jq로 메트릭 추출 (null 체크 개선)
        AVG_DURATION=$(jq -r '.metrics.http_req_duration.values.avg // "N/A"' "$SUMMARY_JSON" 2>/dev/null)
        P50_DURATION=$(jq -r '.metrics.http_req_duration.values.p50 // "N/A"' "$SUMMARY_JSON" 2>/dev/null)
        P95_DURATION=$(jq -r '.metrics.http_req_duration.values.p95 // "N/A"' "$SUMMARY_JSON" 2>/dev/null)
        P99_DURATION=$(jq -r '.metrics.http_req_duration.values.p99 // "N/A"' "$SUMMARY_JSON" 2>/dev/null)
        MAX_DURATION=$(jq -r '.metrics.http_req_duration.values.max // "N/A"' "$SUMMARY_JSON" 2>/dev/null)
        REQ_COUNT=$(jq -r '.metrics.http_reqs.values.count // "N/A"' "$SUMMARY_JSON" 2>/dev/null)
        REQ_RATE=$(jq -r '.metrics.http_reqs.values.rate // "N/A"' "$SUMMARY_JSON" 2>/dev/null)
        FAIL_RATE=$(jq -r '.metrics.http_req_failed.values.rate // "N/A"' "$SUMMARY_JSON" 2>/dev/null)
        DATA_SENT=$(jq -r '.metrics.data_sent.values.count // "N/A"' "$SUMMARY_JSON" 2>/dev/null)
        DATA_RECEIVED=$(jq -r '.metrics.data_received.values.count // "N/A"' "$SUMMARY_JSON" 2>/dev/null)

        # null 값 검증
        if [ "$AVG_DURATION" = "N/A" ] || [ "$AVG_DURATION" = "null" ]; then
            echo -e "${YELLOW}⚠️  메트릭을 추출할 수 없습니다. summary JSON 파일을 확인하세요.${NC}"
            echo -e "${BLUE}디버그 정보:${NC}"
            echo -e "${YELLOW}   Summary JSON:${NC} $SUMMARY_JSON"
            echo -e "${YELLOW}   파일 크기:${NC} $(wc -c < "$SUMMARY_JSON" 2>/dev/null || echo "0") bytes"
            echo -e "${YELLOW}   첫 100자:${NC}"
            head -c 100 "$SUMMARY_JSON" 2>/dev/null || echo "(파일을 읽을 수 없음)"
            echo ""
        else
            # 요약 정보를 파일로도 저장
            {
                echo "=================================================="
                echo "K6 테스트 결과 요약 - $(date)"
                echo "=================================================="
                echo "테스트 타입: $TEST_TYPE"
                echo "대상 URL: $BASE_URL"
                echo "결과 파일 (JSONL): $RESULT_FILE"
                echo "요약 JSON: $SUMMARY_JSON"
                echo ""
                echo "📈 성능 지표:"
                echo "   평균 응답 시간: ${AVG_DURATION}ms"
                echo "   50% 응답 시간: ${P50_DURATION}ms"
                echo "   95% 응답 시간: ${P95_DURATION}ms"
                echo "   99% 응답 시간: ${P99_DURATION}ms"
                echo "   최대 응답 시간: ${MAX_DURATION}ms"
                echo ""
                echo "📊 요청 통계:"
                echo "   총 요청 수: ${REQ_COUNT}"
                echo "   요청 처리율: ${REQ_RATE} req/s"
                echo "   실패율: ${FAIL_RATE}"
                echo ""
                echo "🌐 네트워크:"
                echo "   데이터 송신: ${DATA_SENT} bytes"
                echo "   데이터 수신: ${DATA_RECEIVED} bytes"
                echo ""
            } > "$SUMMARY_FILE"

            echo -e "${BLUE}📈 테스트 결과 요약:${NC}"
            echo -e "${YELLOW}   평균 응답 시간:${NC} ${AVG_DURATION}ms"
            echo -e "${YELLOW}   95% 응답 시간:${NC} ${P95_DURATION}ms"
            echo -e "${YELLOW}   최대 응답 시간:${NC} ${MAX_DURATION}ms"
            echo -e "${YELLOW}   총 요청 수:${NC} ${REQ_COUNT}"
            echo -e "${YELLOW}   실패율:${NC} ${FAIL_RATE}"
            echo ""
            echo -e "${GREEN}✅ 요약 파일:${NC} $SUMMARY_FILE"
        fi
    else
        echo -e "${RED}❌ Summary JSON 파일이 생성되지 않았습니다: $SUMMARY_JSON${NC}"
        echo -e "${YELLOW}💡 k6가 올바르게 실행되었는지 확인하세요.${NC}"
    fi
else
    echo -e "${YELLOW}⚠️  jq가 설치되지 않아 메트릭 요약을 표시할 수 없습니다${NC}"
    echo -e "${YELLOW}💡 설치 방법: brew install jq (macOS) 또는 sudo apt install jq (Ubuntu)${NC}"
fi

echo ""
echo -e "${BLUE}🔍 결과 분석 명령어:${NC}"
echo -e "${YELLOW}   상세 분석:${NC} ./simple-analyze.sh $RESULT_FILE"
echo -e "${YELLOW}   요약 보기:${NC} cat $SUMMARY_FILE"
echo -e "${YELLOW}   요약 JSON:${NC} cat $SUMMARY_JSON | jq ."
echo -e "${YELLOW}   JSONL 전체:${NC} cat $RESULT_FILE | head -20"
echo -e "${YELLOW}   최신 결과들:${NC} ls -la $RESULTS_DIR/"
echo ""
echo -e "${GREEN}감사합니다! 🎉${NC}"
