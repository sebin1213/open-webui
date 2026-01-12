#!/bin/bash

# K6 테스트 데이터 정리 스크립트

set -e

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}"
echo "=================================================="
echo "     K6 테스트 데이터 정리 도구"
echo "=================================================="
echo -e "${NC}"

# 1. K6 결과 파일 보존 (정리하지 않음)
echo -e "${BLUE}📊 K6 결과 파일 보존 중...${NC}"
RESULTS_CLEANED=0

if [ -d "results/" ]; then
    TOTAL_JSON=$(find results/ -name "k6-*.json" 2>/dev/null | wc -l)
    TOTAL_TXT=$(find results/ -name "k6-*.txt" 2>/dev/null | wc -l)

    echo -e "${GREEN}   ✅ ${TOTAL_JSON}개 JSON 결과 파일 보존됨${NC}"
    echo -e "${GREEN}   ✅ ${TOTAL_TXT}개 TXT 요약 파일 보존됨${NC}"
    echo -e "${BLUE}   💡 결과 파일들은 분석용으로 보존됩니다${NC}"
else
    echo -e "${YELLOW}   📁 results 폴더가 없습니다${NC}"
fi

# 2. API 기반 통합 데이터 정리 안내
echo -e "${BLUE}🔄 API 기반 통합 데이터 정리 시작${NC}"
echo -e "${BLUE}   💡 테스트 계정의 파일 삭제 시 다음이 자동으로 처리됩니다:${NC}"
echo -e "${BLUE}     • 물리적 파일 삭제 (data/uploads)${NC}"
echo -e "${BLUE}     • 데이터베이스 레코드 삭제${NC}"
echo -e "${BLUE}     • Vector DB 컬렉션 정리${NC}"
echo -e "${BLUE}     • Storage 메타데이터 정리${NC}"

# 3. 테스트 계정 기반 통합 데이터 정리 (핵심 기능)
echo -e "${YELLOW}🧹 테스트 계정 데이터 통합 정리 중...${NC}"

# 기본 설정값 사용
BASE_URL="http://localhost:8088"
TEST_EMAIL="test@mail.com"
TEST_PASSWORD="1234"

# 환경변수로 오버라이드 가능
BASE_URL=${CLEANUP_BASE_URL:-$BASE_URL}
TEST_EMAIL=${CLEANUP_EMAIL:-$TEST_EMAIL}
TEST_PASSWORD=${CLEANUP_PASSWORD:-$TEST_PASSWORD}

# 정리 결과 추적 변수
CHATS_CLEANED=0
FILES_CLEANED=0
KNOWLEDGE_CLEANED=0
ERRORS=0

if [ -n "$CLEANUP_TOKEN" ] || ([ -n "$TEST_EMAIL" ] && [ -n "$TEST_PASSWORD" ]); then
    echo -e "${BLUE}   🔑 테스트 계정 인증 시도 중...${NC}"

    # 토큰이 없으면 로그인 시도
    if [ -z "$CLEANUP_TOKEN" ]; then
        LOGIN_RESPONSE=$(curl -s -X POST "$BASE_URL/api/v1/auths/signin" \
            -H "Content-Type: application/json" \
            -d "{\"email\":\"$TEST_EMAIL\",\"password\":\"$TEST_PASSWORD\"}" || echo "")

        if echo "$LOGIN_RESPONSE" | grep -q "token"; then
            CLEANUP_TOKEN=$(echo "$LOGIN_RESPONSE" | jq -r '.token' 2>/dev/null || echo "")
            echo -e "${GREEN}   ✅ 테스트 계정 로그인 성공${NC}"
        else
            echo -e "${RED}   ❌ 테스트 계정 로그인 실패 - 데이터 정리 건너뜀${NC}"
            echo -e "${YELLOW}   💡 로그인 응답: ${LOGIN_RESPONSE}${NC}"
        fi
    fi

    # 토큰이 있으면 테스트 계정의 모든 데이터 정리
    if [ -n "$CLEANUP_TOKEN" ]; then
        echo -e "${BLUE}   📊 테스트 계정 데이터 분석 중...${NC}"

        # A. 채팅 데이터 정리
        echo -e "${BLUE}   💬 채팅 데이터 정리 중...${NC}"
        CHATS_RESPONSE=$(curl -s -H "Authorization: Bearer $CLEANUP_TOKEN" "$BASE_URL/api/v1/chats/" || echo "[]")
        CHAT_IDS=$(echo "$CHATS_RESPONSE" | jq -r '.[].id' 2>/dev/null || echo "")

        if [ -n "$CHAT_IDS" ] && [ "$CHAT_IDS" != "" ]; then
            CHAT_COUNT=$(echo "$CHAT_IDS" | wc -l | tr -d ' ')
            echo -e "${YELLOW}   발견된 테스트 계정 채팅: ${CHAT_COUNT}개${NC}"

            read -p "   테스트 계정의 모든 채팅을 삭제하시겠습니까? (y/N): " -n 1 -r
            echo
            if [[ $REPLY =~ ^[Yy]$ ]]; then
                echo "$CHAT_IDS" | while read chat_id; do
                    if [ -n "$chat_id" ] && [ "$chat_id" != "null" ]; then
                        DELETE_RESULT=$(curl -s -w "%{http_code}" -X DELETE -H "Authorization: Bearer $CLEANUP_TOKEN" "$BASE_URL/api/v1/chats/$chat_id")
                        if [[ $DELETE_RESULT == *"200" ]]; then
                            CHATS_CLEANED=$((CHATS_CLEANED + 1))
                        else
                            ERRORS=$((ERRORS + 1))
                        fi
                    fi
                done
                echo -e "${GREEN}   ✅ 채팅 삭제 완료: ${CHATS_CLEANED}개${NC}"
            else
                echo -e "${YELLOW}   ⏭️ 채팅 삭제 건너뜀${NC}"
            fi
        else
            echo -e "${GREEN}   ✅ 삭제할 채팅이 없습니다${NC}"
        fi

        # B. 지식기반 데이터 정리
        echo -e "${BLUE}   🧠 지식기반 데이터 정리 중...${NC}"
        KNOWLEDGE_RESPONSE=$(curl -s -H "Authorization: Bearer $CLEANUP_TOKEN" "$BASE_URL/api/v1/knowledge/" || echo "[]")
        KNOWLEDGE_IDS=$(echo "$KNOWLEDGE_RESPONSE" | jq -r '.[].id' 2>/dev/null || echo "")

        if [ -n "$KNOWLEDGE_IDS" ] && [ "$KNOWLEDGE_IDS" != "" ]; then
            KNOWLEDGE_COUNT=$(echo "$KNOWLEDGE_IDS" | wc -l | tr -d ' ')
            echo -e "${YELLOW}   발견된 테스트 계정 지식기반: ${KNOWLEDGE_COUNT}개${NC}"

            read -p "   테스트 계정의 모든 지식기반을 초기화하시겠습니까? (y/N): " -n 1 -r
            echo
            if [[ $REPLY =~ ^[Yy]$ ]]; then
                echo "$KNOWLEDGE_IDS" | while read kb_id; do
                    if [ -n "$kb_id" ] && [ "$kb_id" != "null" ]; then
                        RESET_RESULT=$(curl -s -w "%{http_code}" -X POST -H "Authorization: Bearer $CLEANUP_TOKEN" "$BASE_URL/api/v1/knowledge/$kb_id/reset")
                        if [[ $RESET_RESULT == *"200" ]]; then
                            KNOWLEDGE_CLEANED=$((KNOWLEDGE_CLEANED + 1))
                        else
                            ERRORS=$((ERRORS + 1))
                        fi
                    fi
                done
                echo -e "${GREEN}   ✅ 지식기반 초기화 완료: ${KNOWLEDGE_CLEANED}개${NC}"
            else
                echo -e "${YELLOW}   ⏭️ 지식기반 초기화 건너뜀${NC}"
            fi
        else
            echo -e "${GREEN}   ✅ 삭제할 지식기반이 없습니다${NC}"
        fi

        # C. 파일 데이터 정리 (파일 + 벡터 DB 자동 정리)
        echo -e "${BLUE}   📁 파일 및 벡터 데이터 정리 중...${NC}"
        FILES_RESPONSE=$(curl -s -H "Authorization: Bearer $CLEANUP_TOKEN" "$BASE_URL/api/v1/files/" || echo "[]")
        FILE_IDS=$(echo "$FILES_RESPONSE" | jq -r '.[].id' 2>/dev/null || echo "")

        if [ -n "$FILE_IDS" ] && [ "$FILE_IDS" != "" ]; then
            FILE_COUNT=$(echo "$FILE_IDS" | wc -l | tr -d ' ')
            echo -e "${YELLOW}   발견된 테스트 계정 파일: ${FILE_COUNT}개${NC}"
            echo -e "${BLUE}   📄 파일 목록:${NC}"
            echo "$FILES_RESPONSE" | jq -r '.[] | "     • " + .filename + " (" + .id + ")"' 2>/dev/null || echo "     • 파일 목록 조회 실패"

            read -p "   테스트 계정의 모든 파일을 삭제하시겠습니까? (파일+벡터DB 통합삭제) (y/N): " -n 1 -r
            echo
            if [[ $REPLY =~ ^[Yy]$ ]]; then
                echo "$FILE_IDS" | while read file_id; do
                    if [ -n "$file_id" ] && [ "$file_id" != "null" ]; then
                        DELETE_RESULT=$(curl -s -w "%{http_code}" -X DELETE -H "Authorization: Bearer $CLEANUP_TOKEN" "$BASE_URL/api/v1/files/$file_id")
                        if [[ $DELETE_RESULT == *"200" ]]; then
                            FILES_CLEANED=$((FILES_CLEANED + 1))
                        else
                            ERRORS=$((ERRORS + 1))
                        fi
                    fi
                done
                echo -e "${GREEN}   ✅ 파일 및 벡터 삭제 완료: ${FILES_CLEANED}개${NC}"
            else
                echo -e "${YELLOW}   ⏭️ 파일 삭제 건너뜀${NC}"
            fi
        else
            echo -e "${GREEN}   ✅ 삭제할 파일이 없습니다${NC}"
        fi

    fi
else
    echo -e "${YELLOW}   🔑 인증 정보가 없어 데이터 정리를 건너뜁니다${NC}"
    echo -e "${BLUE}   💡 환경변수 설정: CLEANUP_TOKEN 또는 CLEANUP_EMAIL/CLEANUP_PASSWORD${NC}"
fi

# 4. 정리 완료 요약
echo ""
echo -e "${GREEN}"
echo "=================================================="
echo "            데이터 정리 완료!"
echo "=================================================="
echo -e "${NC}"

echo -e "${BLUE}📊 테스트 계정 데이터 정리 결과:${NC}"
echo -e "${GREEN}   • 테스트 결과 파일:${NC} 보존됨 (분석용)"
echo -e "${YELLOW}   • 호스트 업로드 파일:${NC} $([ "$DOCKER_CLEANUP" = true ] && echo "정리됨" || echo "건너뜀")"
echo -e "${GREEN}   • 테스트 계정 채팅:${NC} ${CHATS_CLEANED}개 삭제"
echo -e "${GREEN}   • 테스트 계정 파일:${NC} ${FILES_CLEANED}개 삭제 (벡터DB 포함)"
echo -e "${GREEN}   • 테스트 계정 지식기반:${NC} ${KNOWLEDGE_CLEANED}개 초기화"
if [ $ERRORS -gt 0 ]; then
    echo -e "${RED}   • 오류 발생:${NC} ${ERRORS}건"
fi
echo -e "${BLUE}   • 다른 사용자 데이터:${NC} 완전 보존됨"
echo -e "${BLUE}   • 시스템 설정:${NC} 완전 보존됨"

echo ""
echo -e "${GREEN}✨ 간소화된 테스트 워크플로우:${NC}"
echo -e "${BLUE}   1. 테스트 실행${NC} → ./run-k6-tests.sh [타입]"
echo -e "${BLUE}   2. 결과 확인${NC} → ./simple-analyze.sh"
echo -e "${BLUE}   3. 데이터 정리${NC} → ./cleanup-test-data.sh"
echo ""
echo -e "${YELLOW}💡 테스트 계정 기반 정리 대상:${NC}"
echo -e "${BLUE}   • 호스트 data/uploads의 k6-test* 파일 삭제${NC}"
echo -e "${BLUE}   • 테스트 계정의 모든 채팅 삭제${NC}"
echo -e "${BLUE}   • 테스트 계정의 모든 파일 삭제 (벡터DB 자동 정리)${NC}"
echo -e "${BLUE}   • 테스트 계정의 모든 지식기반 초기화${NC}"
echo -e "${BLUE}   • 테스트 결과 파일은 영구 보존${NC}"
echo -e "${BLUE}   • 다른 사용자 데이터와 시스템 설정은 완전 보존${NC}"
echo ""

echo -e "${GREEN}테스트 계정 데이터 정리 완료! 🧹✨${NC}"