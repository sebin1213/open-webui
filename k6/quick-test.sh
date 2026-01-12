#!/bin/bash

# Open WebUI 빠른 기능 검증 스크립트
# 서버 업데이트 후 핵심 기능 정상 동작 확인용

set -e

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m'

# 기본 설정
BASE_URL=${1:-"http://localhost:8088"}
TEST_EMAIL=${2:-"test@mail.com"}
TEST_PASSWORD=${3:-"1234"}
TEST_MODE=${4:-"functional"}  # functional, smoke, full

echo -e "${CYAN}"
echo "=================================================="
echo "  Open WebUI 서버 업데이트 후 기능 검증"
echo "=================================================="
echo -e "${NC}"
echo -e "${YELLOW}대상 서버:${NC} $BASE_URL"
echo -e "${YELLOW}테스트 계정:${NC} $TEST_EMAIL"
echo -e "${YELLOW}검증 모드:${NC} $TEST_MODE"
echo ""
echo -e "${BLUE}💡 검증 모드 설명 (기능 검증 우선):${NC}"
echo -e "${GREEN}   smoke${NC}      - 모든 API 순차 호출 (부하 없음, 1-2분) ⭐ 권장"
echo -e "${YELLOW}   functional${NC} - smoke + 동시성 안정성 검증 (3-4분)"
echo -e "${RED}   full${NC}        - functional + 부하 한계 테스트 (10-15분)"
echo ""
echo -e "${CYAN}📋 Smoke 모드 검증 항목 (부하 최소화):${NC}"
echo -e "   • VUS: 1명 (부하 없이 순차 실행)"
echo -e "   • 모든 API 엔드포인트 1회 이상 호출"
echo -e "   • 파일 업로드 기능 확인"
echo -e "   • 실제 AI 메시지 1건 전송 및 응답 확인"
echo ""

# 테스트 시작 시간 기록
START_TIME=$(date +%s)

# 서버 상태 확인
echo -e "${BLUE}[Step 1/5] 🔍 서버 연결 확인${NC}"
if curl -s --max-time 5 "$BASE_URL/health" > /dev/null 2>&1; then
    echo -e "${GREEN}✅ 서버 응답 정상${NC}"
else
    echo -e "${RED}❌ 서버에 연결할 수 없습니다: $BASE_URL${NC}"
    echo -e "${YELLOW}💡 서버가 실행 중인지 확인하세요${NC}"
    exit 1
fi
echo ""

# 결과 저장 디렉토리 생성
RESULTS_DIR="results"
mkdir -p "$RESULTS_DIR"
TIMESTAMP=$(date +"%Y%m%d-%H%M%S")

# 테스트 결과 추적
TESTS_PASSED=0
TESTS_FAILED=0
TESTS_WARNING=0

# ============================================
# Smoke Test (모든 모드에서 실행)
# ============================================
if [ "$TEST_MODE" = "smoke" ] || [ "$TEST_MODE" = "functional" ] || [ "$TEST_MODE" = "full" ]; then
    echo -e "${BLUE}[Step 2/5] 🔥 전체 API 기능 검증 (30초)${NC}"
    echo -e "${CYAN}   → 모든 API 순차 호출 (부하 없음, VUS=1)${NC}"

    # test.pdf 파일 존재 확인 및 생성
    TEST_PDF="test.pdf"
    if [ ! -f "$TEST_PDF" ]; then
        echo -e "${YELLOW}   📄 test.pdf 생성 중...${NC}"
        # 간단한 PDF 생성
        cat > "$TEST_PDF" << 'PDFEOF'
%PDF-1.4
1 0 obj
<<
/Type /Catalog
/Pages 2 0 R
>>
endobj
2 0 obj
<<
/Type /Pages
/Kids [3 0 R]
/Count 1
>>
endobj
3 0 obj
<<
/Type /Page
/Parent 2 0 R
/MediaBox [0 0 612 792]
/Contents 4 0 R
/Resources <<
/Font <<
/F1 5 0 R
>>
>>
>>
endobj
4 0 obj
<<
/Length 200
>>
stream
BT
/F1 12 Tf
50 750 Td
(Open WebUI Test Document) Tj
0 -20 Td
(Quick Test - API Verification) Tj
0 -20 Td
(This is a test PDF file for file upload testing.) Tj
ET
endstream
endobj
5 0 obj
<<
/Type /Font
/Subtype /Type1
/BaseFont /Helvetica
>>
endobj
xref
0 6
0000000000 65535 f
0000000010 00000 n
0000000079 00000 n
0000000173 00000 n
0000000370 00000 n
0000000624 00000 n
trailer
<<
/Size 6
/Root 1 0 R
>>
startxref
724
%%EOF
PDFEOF
        echo -e "${GREEN}   ✅ test.pdf 생성 완료${NC}"
    else
        echo -e "${GREEN}   ✅ test.pdf 파일 확인됨${NC}"
    fi

    SMOKE_RESULT="$RESULTS_DIR/quick-smoke-${TIMESTAMP}.json"
    SMOKE_SUMMARY="$RESULTS_DIR/quick-smoke-summary-${TIMESTAMP}.json"

    # 전체 API 테스트 (기능 검증 우선, 부하 최소화)
    if k6 run \
        --out json="$SMOKE_RESULT" \
        --summary-export "$SMOKE_SUMMARY" \
        -e BASE_URL="$BASE_URL" \
        -e EMAIL="$TEST_EMAIL" \
        -e PASSWORD="$TEST_PASSWORD" \
        -e VUS=1 \
        -e DURATION=30s \
        -e TEST_TYPE=simple \
        -e TEST_DOCUMENTS=true \
        -e TEST_FILE_UPLOAD=true \
        --quiet \
        k6-user-load-test.js 2>/dev/null; then

        echo -e "${GREEN}✅ 전체 API 검증 통과${NC}"
        TESTS_PASSED=$((TESTS_PASSED + 1))
    else
        echo -e "${RED}❌ 전체 API 검증 실패 - 서버 기능에 문제가 있습니다${NC}"
        TESTS_FAILED=$((TESTS_FAILED + 1))

        if [ "$TEST_MODE" = "smoke" ]; then
            echo -e "${RED}Smoke 모드에서 실패 발생 - 테스트 중단${NC}"
            exit 1
        fi
    fi
    echo ""
fi

# ============================================
# Functional Test (functional, full 모드)
# ============================================
if [ "$TEST_MODE" = "functional" ] || [ "$TEST_MODE" = "full" ]; then
    echo -e "${BLUE}[Step 3/5] 📋 확장 기능 집중 검증 (1-2분)${NC}"
    echo -e "${CYAN}   → 문서, 지식베이스, 프롬프트, 도구 등 확장 기능 집중 테스트${NC}"

    FUNC_RESULT="$RESULTS_DIR/quick-functional-${TIMESTAMP}.json"
    FUNC_SUMMARY="$RESULTS_DIR/quick-functional-summary-${TIMESTAMP}.json"

    if k6 run \
        --out json="$FUNC_RESULT" \
        --summary-export "$FUNC_SUMMARY" \
        -e BASE_URL="$BASE_URL" \
        -e EMAIL="$TEST_EMAIL" \
        -e PASSWORD="$TEST_PASSWORD" \
        -e VUS=3 \
        -e DURATION=90s \
        -e TEST_TYPE=simple \
        -e TEST_DOCUMENTS=true \
        --quiet \
        k6-user-load-test.js 2>/dev/null; then

        echo -e "${GREEN}✅ 확장 기능 검증 통과${NC}"
        TESTS_PASSED=$((TESTS_PASSED + 1))
    else
        echo -e "${YELLOW}⚠️  확장 기능 검증 중 일부 이슈 발생${NC}"
        TESTS_WARNING=$((TESTS_WARNING + 1))
    fi
    echo ""
fi

# ============================================
# AI Chat Test (모든 모드에서 실제 AI 호출)
# ============================================
if [ "$TEST_MODE" = "smoke" ] || [ "$TEST_MODE" = "functional" ] || [ "$TEST_MODE" = "full" ]; then
    echo -e "${BLUE}[Step 4/5] 💬 AI 채팅 기능 검증 (1건 전송)${NC}"
    echo -e "${CYAN}   → 채팅방 생성 + AI 메시지 1건 전송 및 응답 확인${NC}"

    CHAT_RESULT="$RESULTS_DIR/quick-chat-${TIMESTAMP}.json"
    CHAT_SUMMARY="$RESULTS_DIR/quick-chat-summary-${TIMESTAMP}.json"

    # 실제 AI 호출 1건만 (기능 검증 목적)
    if k6 run \
        --out json="$CHAT_RESULT" \
        --summary-export "$CHAT_SUMMARY" \
        -e BASE_URL="$BASE_URL" \
        -e TEST_EMAIL="$TEST_EMAIL" \
        -e TEST_PASSWORD="$TEST_PASSWORD" \
        -e WORKSPACE_ID="test_workspace" \
        -e SEND_MESSAGES=true \
        -e MESSAGE_DELAY=5 \
        -e VUS=1 \
        -e DURATION=35s \
        -e TEST_TYPE=simple \
        --quiet \
        k6-chat-message-test.js 2>/dev/null; then

        echo -e "${GREEN}✅ 실제 AI 채팅 검증 통과${NC}"
        TESTS_PASSED=$((TESTS_PASSED + 1))
    else
        echo -e "${YELLOW}⚠️  AI 채팅 기능 검증 중 일부 이슈 발생${NC}"
        echo -e "${CYAN}   💡 모델 설정 및 AI 서비스 상태를 확인하세요${NC}"
        TESTS_WARNING=$((TESTS_WARNING + 1))
    fi
    echo ""
fi

# ============================================
# Load Test (full 모드만)
# ============================================
if [ "$TEST_MODE" = "full" ]; then
    echo -e "${BLUE}[Step 5/5] 📈 부하 테스트 (3분)${NC}"
    echo -e "${CYAN}   → 10명 동시 사용자 부하 테스트${NC}"

    LOAD_RESULT="$RESULTS_DIR/quick-load-${TIMESTAMP}.json"
    LOAD_SUMMARY="$RESULTS_DIR/quick-load-summary-${TIMESTAMP}.json"

    if k6 run \
        --out json="$LOAD_RESULT" \
        --summary-export "$LOAD_SUMMARY" \
        -e BASE_URL="$BASE_URL" \
        -e EMAIL="$TEST_EMAIL" \
        -e PASSWORD="$TEST_PASSWORD" \
        -e VUS=10 \
        -e DURATION=3m \
        -e TEST_TYPE=simple \
        --quiet \
        k6-user-load-test.js 2>/dev/null; then

        echo -e "${GREEN}✅ 부하 테스트 통과${NC}"
        TESTS_PASSED=$((TESTS_PASSED + 1))
    else
        echo -e "${YELLOW}⚠️  부하 테스트에서 이슈 발생${NC}"
        TESTS_WARNING=$((TESTS_WARNING + 1))
    fi
    echo ""
fi

# ============================================
# 최종 결과 요약
# ============================================
END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))

echo -e "${CYAN}"
echo "=================================================="
echo "           기능 검증 완료"
echo "=================================================="
echo -e "${NC}"

echo -e "${BLUE}📊 테스트 결과 요약:${NC}"
echo -e "${GREEN}   ✅ 통과: ${TESTS_PASSED}개${NC}"
if [ $TESTS_WARNING -gt 0 ]; then
    echo -e "${YELLOW}   ⚠️  경고: ${TESTS_WARNING}개${NC}"
fi
if [ $TESTS_FAILED -gt 0 ]; then
    echo -e "${RED}   ❌ 실패: ${TESTS_FAILED}개${NC}"
fi
echo -e "${CYAN}   ⏱️  소요 시간: ${DURATION}초${NC}"
echo ""

# 최종 판정
if [ $TESTS_FAILED -gt 0 ]; then
    echo -e "${RED}❌ 기능 검증 실패 - 핵심 API에 문제가 있습니다${NC}"
    EXIT_CODE=1
elif [ $TESTS_WARNING -gt 0 ]; then
    echo -e "${YELLOW}⚠️  기능 검증 완료 (일부 경고 있음)${NC}"
    echo -e "${YELLOW}💡 기본 기능은 정상이나 일부 API 확인 필요${NC}"
    EXIT_CODE=0
else
    echo -e "${GREEN}✅ 기능 검증 성공 - 모든 API 정상 동작${NC}"
    EXIT_CODE=0
fi

echo ""
echo -e "${BLUE}📁 상세 결과 파일:${NC}"
echo -e "${CYAN}   $RESULTS_DIR/quick-*-${TIMESTAMP}.*${NC}"
echo ""

echo -e "${BLUE}🔍 추가 검증 방법:${NC}"
echo -e "${GREEN}   기능 재검증:${NC} ./quick-test.sh $BASE_URL $TEST_EMAIL $TEST_PASSWORD smoke"
echo -e "${YELLOW}   안정성 검증:${NC} ./quick-test.sh $BASE_URL $TEST_EMAIL $TEST_PASSWORD functional"
echo -e "${RED}   부하 테스트:${NC}  ./quick-test.sh $BASE_URL $TEST_EMAIL $TEST_PASSWORD full"
echo -e "${CYAN}   상세 분석:${NC}    ./simple-analyze.sh $RESULTS_DIR/quick-smoke-${TIMESTAMP}.json"
echo ""

echo -e "${BLUE}📝 사용법:${NC}"
echo "   ./quick-test.sh [URL] [이메일] [비밀번호] [모드]"
echo "   모드: smoke (기능검증), functional (안정성검증), full (부하테스트)"
echo ""
echo -e "${GREEN}검증 완료! 🎉${NC}"

exit $EXIT_CODE