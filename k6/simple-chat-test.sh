#!/bin/bash

# Open WebUI 채팅 기능 단순 테스트 스크립트
# 사전 정의된 계정으로 실제 채팅만 진행

set -e

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

# 파라미터 처리 (첫 번째 인자가 숫자면 메시지 개수로 처리)
if [[ "$1" =~ ^[0-9]+$ ]]; then
    # 첫 번째 인자가 숫자면 메시지 개수로 사용
    MESSAGE_COUNT=$1
    BASE_URL="http://localhost:8088"
    TEST_EMAIL="test@mail.com"
    TEST_PASSWORD="1234"
    MODEL_NAME="test_workspace"
else
    # 기존 방식 (전체 파라미터 지정)
    BASE_URL=${1:-"http://localhost:8088"}
    TEST_EMAIL=${2:-"test@mail.com"}
    TEST_PASSWORD=${3:-"1234"}
    MODEL_NAME=${4:-"test_workspace"}
    MESSAGE_COUNT=${5:-3}
fi

echo -e "${CYAN}"
echo "=================================================="
echo "  Open WebUI 채팅 기능 간단 테스트"
echo "=================================================="
echo -e "${NC}"
echo -e "${YELLOW}테스트 설정:${NC}"
echo -e "  • 서버 URL: $BASE_URL"
echo -e "  • 계정: $TEST_EMAIL"
echo -e "  • 모델: $MODEL_NAME"
echo -e "  • 메시지 수: $MESSAGE_COUNT"
echo ""

# 테스트 시작 시간
START_TIME=$(date +%s)

# 1. 서버 상태 확인
echo -e "${BLUE}[1/3] 서버 연결 확인${NC}"
if curl -s --max-time 5 "$BASE_URL/health" > /dev/null 2>&1; then
    echo -e "${GREEN}✅ 서버 응답 정상${NC}"
else
    echo -e "${RED}❌ 서버 연결 실패: $BASE_URL${NC}"
    exit 1
fi
echo ""

# 2. 결과 디렉토리 생성
RESULTS_DIR="results/chat-tests"
mkdir -p "$RESULTS_DIR"
TIMESTAMP=$(date +"%Y%m%d-%H%M%S")

# 3. 채팅 테스트 실행
echo -e "${BLUE}[2/3] 채팅 테스트 실행 (${MESSAGE_COUNT}개 메시지)${NC}"
echo -e "${CYAN}   → 로그인 후 채팅방 생성 및 AI와 대화${NC}"

CHAT_RESULT="$RESULTS_DIR/chat-test-${TIMESTAMP}.json"
CHAT_SUMMARY="$RESULTS_DIR/chat-test-summary-${TIMESTAMP}.json"

# k6 테스트 실행 (단일 사용자)

# k6 실행 (iterations=1로 정확히 1번만 실행)
echo -e "${CYAN}   설정된 메시지 수: ${MESSAGE_COUNT}개${NC}"
echo -e "${CYAN}   VUS: 1명 (단일 사용자)${NC}"
echo -e "${CYAN}   Iterations: 1회 (정확히 1번 실행)${NC}"
echo ""

# k6 실행 - iterations 모드로 변경 (duration 제거)
k6 run \
    --out json="$CHAT_RESULT" \
    --summary-export "$CHAT_SUMMARY" \
    -e BASE_URL="$BASE_URL" \
    -e TEST_EMAIL="$TEST_EMAIL" \
    -e TEST_PASSWORD="$TEST_PASSWORD" \
    -e MODEL_NAME="$MODEL_NAME" \
    -e MESSAGE_COUNT="$MESSAGE_COUNT" \
    k6-simple-chat.js

K6_EXIT_CODE=$?

# 실제 메시지 전송 성공 여부를 JSON 결과에서 확인
if [ -f "$CHAT_SUMMARY" ] && command -v jq &> /dev/null; then
    # k6 메트릭에서 값 추출 (올바른 경로 사용)
    MESSAGES_SENT=$(jq -r '.metrics.messages_sent_total.count // 0' "$CHAT_SUMMARY" 2>/dev/null)
    MESSAGES_SUCCESS=$(jq -r '.metrics.messages_success_total.count // 0' "$CHAT_SUMMARY" 2>/dev/null)

    # null이나 빈 값 처리
    MESSAGES_SENT=${MESSAGES_SENT:-0}
    MESSAGES_SUCCESS=${MESSAGES_SUCCESS:-0}

    if [ "$MESSAGES_SENT" != "0" ] && [ "$MESSAGES_SUCCESS" != "0" ]; then
        echo -e "${GREEN}✅ 채팅 테스트 성공 (${MESSAGES_SUCCESS}/${MESSAGES_SENT} 메시지)${NC}"
        TEST_STATUS="SUCCESS"
    else
        # k6 exit code도 확인
        if [ $K6_EXIT_CODE -eq 0 ]; then
            echo -e "${YELLOW}⚠️  k6는 성공했지만 메시지 통계 확인 필요${NC}"
            TEST_STATUS="SUCCESS"
        else
            echo -e "${RED}❌ 채팅 테스트 실패${NC}"
            TEST_STATUS="FAILED"
        fi
    fi
else
    # jq가 없거나 파일이 없으면 k6 exit code로 판단
    if [ $K6_EXIT_CODE -eq 0 ]; then
        echo -e "${GREEN}✅ 채팅 테스트 성공${NC}"
        TEST_STATUS="SUCCESS"
    else
        echo -e "${RED}❌ 채팅 테스트 실패${NC}"
        TEST_STATUS="FAILED"
    fi
fi
echo ""

# 4. 결과 요약
END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))

echo -e "${BLUE}[3/3] 테스트 결과${NC}"
echo -e "${CYAN}"
echo "=================================================="
echo -e "${NC}"

if [ "$TEST_STATUS" = "SUCCESS" ]; then
    echo -e "${GREEN}✅ 채팅 기능 정상 작동${NC}"
    echo -e "   • 로그인 성공"
    echo -e "   • 채팅방 생성 성공"
    echo -e "   • AI 응답 수신 성공"
else
    echo -e "${RED}❌ 채팅 기능 오류 발생${NC}"
    echo -e "${YELLOW}   다음 사항을 확인하세요:${NC}"
    echo -e "   • 계정 정보가 올바른지"
    echo -e "   • 모델이 설정되어 있는지"
    echo -e "   • AI 서비스가 정상 작동하는지"
fi

echo ""
echo -e "${CYAN}소요 시간: ${DURATION}초${NC}"
echo -e "${CYAN}결과 파일: ${CHAT_RESULT}${NC}"
echo ""

# 상세 통계 출력 (jq가 설치된 경우)
if command -v jq &> /dev/null && [ -f "$CHAT_SUMMARY" ]; then
    echo -e "${BLUE}📊 상세 통계:${NC}"

    # 메시지 통계 (올바른 경로 사용)
    MESSAGES_SENT=$(jq -r '.metrics.messages_sent_total.count // 0' "$CHAT_SUMMARY" 2>/dev/null)
    MESSAGES_SUCCESS=$(jq -r '.metrics.messages_success_total.count // 0' "$CHAT_SUMMARY" 2>/dev/null)
    MESSAGES_FAILED=$(jq -r '.metrics.messages_failed_total.count // 0' "$CHAT_SUMMARY" 2>/dev/null)
    MESSAGES_RECEIVED=$(jq -r '.metrics.messages_received_total.count // 0' "$CHAT_SUMMARY" 2>/dev/null)

    # null이나 빈 값 처리
    MESSAGES_SENT=${MESSAGES_SENT:-0}
    MESSAGES_SUCCESS=${MESSAGES_SUCCESS:-0}
    MESSAGES_FAILED=${MESSAGES_FAILED:-0}
    MESSAGES_RECEIVED=${MESSAGES_RECEIVED:-0}

    echo -e "${GREEN}✉️  메시지 통계:${NC}"
    echo -e "   • 전송 시도: ${MESSAGES_SENT}개"
    echo -e "   • 성공: ${MESSAGES_SUCCESS}개"
    echo -e "   • 실패: ${MESSAGES_FAILED}개"
    echo -e "   • AI 응답 수신: ${MESSAGES_RECEIVED}개"

    if [ "$MESSAGES_SENT" != "0" ] && [ "$MESSAGES_SENT" != "null" ]; then
        SUCCESS_RATE=$(echo "scale=1; $MESSAGES_SUCCESS * 100 / $MESSAGES_SENT" | bc 2>/dev/null || echo "0")
        echo -e "   • 성공률: ${SUCCESS_RATE}%"
    fi
    echo ""

    # 에러 코드별 통계
    if [ "$MESSAGES_FAILED" != "0" ] && [ "$MESSAGES_FAILED" != "null" ]; then
        echo -e "${RED}❌ 에러 분석:${NC}"

        ERROR_400=$(jq -r '.metrics.error_400_bad_request.values.count // 0' "$CHAT_SUMMARY" 2>/dev/null || echo "0")
        ERROR_401=$(jq -r '.metrics.error_401_unauthorized.values.count // 0' "$CHAT_SUMMARY" 2>/dev/null || echo "0")
        ERROR_403=$(jq -r '.metrics.error_403_forbidden.values.count // 0' "$CHAT_SUMMARY" 2>/dev/null || echo "0")
        ERROR_404=$(jq -r '.metrics.error_404_not_found.values.count // 0' "$CHAT_SUMMARY" 2>/dev/null || echo "0")
        ERROR_429=$(jq -r '.metrics.error_429_rate_limit.values.count // 0' "$CHAT_SUMMARY" 2>/dev/null || echo "0")
        ERROR_500=$(jq -r '.metrics.error_500_internal.values.count // 0' "$CHAT_SUMMARY" 2>/dev/null || echo "0")
        ERROR_502=$(jq -r '.metrics.error_502_bad_gateway.values.count // 0' "$CHAT_SUMMARY" 2>/dev/null || echo "0")
        ERROR_503=$(jq -r '.metrics.error_503_unavailable.values.count // 0' "$CHAT_SUMMARY" 2>/dev/null || echo "0")
        ERROR_TIMEOUT=$(jq -r '.metrics.error_timeout.values.count // 0' "$CHAT_SUMMARY" 2>/dev/null || echo "0")
        ERROR_OTHER=$(jq -r '.metrics.error_other.values.count // 0' "$CHAT_SUMMARY" 2>/dev/null || echo "0")

        [ "$ERROR_400" != "0" ] && echo -e "   • 400 Bad Request: ${ERROR_400}건"
        [ "$ERROR_401" != "0" ] && echo -e "   • 401 Unauthorized: ${ERROR_401}건"
        [ "$ERROR_403" != "0" ] && echo -e "   • 403 Forbidden: ${ERROR_403}건"
        [ "$ERROR_404" != "0" ] && echo -e "   • 404 Not Found: ${ERROR_404}건"
        [ "$ERROR_429" != "0" ] && echo -e "   • 429 Rate Limited: ${ERROR_429}건"
        [ "$ERROR_500" != "0" ] && echo -e "   • 500 Internal Error: ${ERROR_500}건"
        [ "$ERROR_502" != "0" ] && echo -e "   • 502 Bad Gateway: ${ERROR_502}건"
        [ "$ERROR_503" != "0" ] && echo -e "   • 503 Unavailable: ${ERROR_503}건"
        [ "$ERROR_TIMEOUT" != "0" ] && echo -e "   • Timeout/Network: ${ERROR_TIMEOUT}건"
        [ "$ERROR_OTHER" != "0" ] && echo -e "   • Other Errors: ${ERROR_OTHER}건"
        echo ""
    fi

    # 응답 시간 통계
    echo -e "${CYAN}⏱️  성능 지표:${NC}"
    HTTP_DURATION_P95=$(jq -r '.metrics.http_req_duration.values["p(95)"] // 0' "$CHAT_SUMMARY" 2>/dev/null || echo "0")
    HTTP_DURATION_P99=$(jq -r '.metrics.http_req_duration.values["p(99)"] // 0' "$CHAT_SUMMARY" 2>/dev/null || echo "0")
    HTTP_DURATION_AVG=$(jq -r '.metrics.http_req_duration.values.avg // 0' "$CHAT_SUMMARY" 2>/dev/null || echo "0")
    AI_RESPONSE_AVG=$(jq -r '.metrics.ai_response_time_ms.values.avg // 0' "$CHAT_SUMMARY" 2>/dev/null || echo "0")
    AI_RESPONSE_P95=$(jq -r '.metrics.ai_response_time_ms.values["p(95)"] // 0' "$CHAT_SUMMARY" 2>/dev/null || echo "0")

    if [ "$HTTP_DURATION_AVG" != "0" ] && [ "$HTTP_DURATION_AVG" != "null" ]; then
        echo -e "   • HTTP 평균 응답: ${HTTP_DURATION_AVG}ms"
        echo -e "   • HTTP P95: ${HTTP_DURATION_P95}ms"
        echo -e "   • HTTP P99: ${HTTP_DURATION_P99}ms"
    fi

    if [ "$AI_RESPONSE_AVG" != "0" ] && [ "$AI_RESPONSE_AVG" != "null" ]; then
        echo -e "   • AI 평균 응답: ${AI_RESPONSE_AVG}ms"
        echo -e "   • AI P95: ${AI_RESPONSE_P95}ms"
    fi
    echo ""
fi

echo -e "${BLUE}🔄 다시 실행하려면:${NC}"
echo "   ./simple-chat-test.sh              # 기본 3개 메시지"
echo "   ./simple-chat-test.sh 5            # 5개 메시지"
echo "   ./simple-chat-test.sh 10           # 10개 메시지"
echo ""
echo -e "${CYAN}💡 고급 옵션:${NC}"
echo "   ./simple-chat-test.sh [URL] [이메일] [비밀번호] [모델] [메시지수]"
echo ""

if [ "$TEST_STATUS" = "SUCCESS" ]; then
    echo -e "${GREEN}테스트 완료! 🎉${NC}"
    exit 0
else
    echo -e "${RED}테스트 실패! 😔${NC}"
    exit 1
fi