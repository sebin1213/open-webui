#!/bin/bash

# 간단한 K6 결과 분석 스크립트 (JSONL 형식 지원)

set -e

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
NC='\033[0m'

RESULT_FILE=${1}

echo -e "${BLUE}"
echo "=================================================="
echo "     K6 테스트 결과 간단 분석기"
echo "=================================================="
echo -e "${NC}"

# 결과 파일 확인
if [ -z "$RESULT_FILE" ]; then
    echo -e "${YELLOW}사용법: ./simple-analyze.sh [결과파일명]${NC}"
    LATEST_FILE=$(ls -t results/*.json 2>/dev/null | head -1)
    if [ -n "$LATEST_FILE" ]; then
        echo -e "${GREEN}최신 파일 사용: $LATEST_FILE${NC}"
        RESULT_FILE="$LATEST_FILE"
    else
        exit 1
    fi
fi

if [ ! -f "$RESULT_FILE" ]; then
    echo -e "${RED}❌ 결과 파일을 찾을 수 없습니다: $RESULT_FILE${NC}"
    exit 1
fi

echo -e "${GREEN}✅ 분석 대상:${NC} $RESULT_FILE"
echo ""

# 기본 통계
echo -e "${PURPLE}📊 기본 통계${NC}"
echo "=================================================="

# HTTP 요청 수
REQ_COUNT=$(grep '"metric":"http_reqs".*"type":"Point"' "$RESULT_FILE" | wc -l)
echo -e "${YELLOW}총 HTTP 요청:${NC} $REQ_COUNT 개"

# 실패한 요청 수
FAILED_COUNT=$(grep '"metric":"http_req_failed".*"value":1' "$RESULT_FILE" | wc -l)
SUCCESS_COUNT=$(grep '"metric":"http_req_failed".*"value":0' "$RESULT_FILE" | wc -l)
if [ $REQ_COUNT -gt 0 ]; then
    FAILURE_RATE=$(echo "scale=4; $FAILED_COUNT / $REQ_COUNT * 100" | bc 2>/dev/null || echo "0")
else
    FAILURE_RATE="0"
fi
echo -e "${YELLOW}성공한 요청:${NC} $SUCCESS_COUNT 개"
echo -e "${YELLOW}실패한 요청:${NC} $FAILED_COUNT 개 (${FAILURE_RATE}%)"

# 실패한 요청 상세 분석
if [ $FAILED_COUNT -gt 0 ]; then
    echo ""
    echo -e "${RED}🚨 실패한 요청 상세 분석${NC}"
    echo "=================================================="
    
    # HTTP 상태코드별 분석
    echo -e "${YELLOW}HTTP 상태코드별 실패 분석:${NC}"
    grep '"metric":"http_req_failed".*"value":1' "$RESULT_FILE" | \
        sed 's/.*"status":"\([^"]*\)".*/\1/' | \
        sort | uniq -c | sort -rn | \
        while read count status; do
            printf "${RED}%-10s${NC} %d 회\n" "HTTP $status:" "$count"
        done
    
    # URL별 실패 분석 (상위 10개)
    echo ""
    echo -e "${YELLOW}실패가 많은 API 엔드포인트 (상위 5개):${NC}"
grep '"metric":"http_req_failed".*"value":1' "$RESULT_FILE" | \
        sed 's/.*"url":"\([^"]*\)".*/\1/' | \
        sed -E 's#https?://[^/]+/##' | \
        sort | uniq -c | sort -rn | head -5 | \
        while read count url; do
            printf "${RED}%-50s${NC} %d 회\n" "$url" "$count"
        done
fi

# 응답 시간 분석
echo ""
echo -e "${PURPLE}⏱️  응답 시간 분석${NC}"
echo "=================================================="

# 응답시간 추출 및 정렬
DURATION_FILE=$(mktemp)
grep '"metric":"http_req_duration".*"type":"Point"' "$RESULT_FILE" | \
    sed 's/.*"value":\([0-9.]*\).*/\1/' | \
    sort -n > "$DURATION_FILE"

if [ -s "$DURATION_FILE" ]; then
    TOTAL_LINES=$(wc -l < "$DURATION_FILE")
    
    # 통계 계산
    MIN_DURATION=$(head -1 "$DURATION_FILE")
    MAX_DURATION=$(tail -1 "$DURATION_FILE")
    AVG_DURATION=$(awk '{sum+=$1} END {printf "%.2f", sum/NR}' "$DURATION_FILE" 2>/dev/null || echo "0")
    
    # 백분위수 계산
    P50_LINE=$(echo "($TOTAL_LINES + 1) / 2" | bc)
    P95_LINE=$(echo "$TOTAL_LINES * 95 / 100" | bc)
    P99_LINE=$(echo "$TOTAL_LINES * 99 / 100" | bc)
    
    P50_DURATION=$(sed -n "${P50_LINE}p" "$DURATION_FILE" 2>/dev/null || echo "0")
    P95_DURATION=$(sed -n "${P95_LINE}p" "$DURATION_FILE" 2>/dev/null || echo "0")
    P99_DURATION=$(sed -n "${P99_LINE}p" "$DURATION_FILE" 2>/dev/null || echo "0")
    
    printf "${YELLOW}%-15s${NC} %.2f ms\n" "최소 응답시간:" "$MIN_DURATION"
    printf "${YELLOW}%-15s${NC} %.2f ms\n" "평균 응답시간:" "$AVG_DURATION"
    printf "${YELLOW}%-15s${NC} %.2f ms\n" "50% 응답시간:" "$P50_DURATION"
    printf "${YELLOW}%-15s${NC} %.2f ms\n" "95% 응답시간:" "$P95_DURATION"
    printf "${YELLOW}%-15s${NC} %.2f ms\n" "99% 응답시간:" "$P99_DURATION"
    printf "${YELLOW}%-15s${NC} %.2f ms\n" "최대 응답시간:" "$MAX_DURATION"
    
    echo ""
    echo -e "${BLUE}📖 응답시간 백분위수 설명:${NC}"
    echo -e "${GREEN}50% (중간값)${NC}: 절반의 사용자가 ${P50_DURATION}ms 이내에 응답을 받음"
    echo -e "${YELLOW}95% (P95)${NC}: 95%의 사용자가 ${P95_DURATION}ms 이내에 응답을 받음"
    echo -e "${RED}99% (P99)${NC}: 99%의 사용자가 ${P99_DURATION}ms 이내에 응답을 받음"
    echo -e "${PURPLE}의미${NC}: P95가 중요한 이유는 대부분의 사용자 경험을 나타내기 때문"
else
    echo "응답시간 데이터를 찾을 수 없습니다."
fi

# 동시 사용자별 응답시간 분석
echo ""
echo -e "${PURPLE}👥 동시 사용자별 성능 분석${NC}"
echo "=================================================="

# VUS (Virtual Users) 데이터 추출
VUS_FILE=$(mktemp)
TIMELINE_FILE=$(mktemp)

# VUS 변화 추적
grep '"metric":"vus".*"type":"Point"' "$RESULT_FILE" | \
    sed 's/.*"time":"\([^"]*\)".*"value":\([0-9]*\).*/\1 \2/' > "$VUS_FILE"

# 시간대별 응답시간과 VUS 매핑
grep '"metric":"http_req_duration".*"type":"Point"' "$RESULT_FILE" | \
    sed 's/.*"time":"\([^"]*\)".*"value":\([0-9.]*\).*/\1 \2/' | \
    head -1000 > "$TIMELINE_FILE"  # 샘플링으로 성능 최적화

if [ -s "$VUS_FILE" ] && [ -s "$TIMELINE_FILE" ]; then
    echo -e "${YELLOW}동시 사용자 수 변화 패턴:${NC}"
    
    # VUS 구간별 분석
    MIN_VUS=$(awk '{print $2}' "$VUS_FILE" | sort -n | head -1)
    MAX_VUS=$(awk '{print $2}' "$VUS_FILE" | sort -n | tail -1)
    
    echo -e "${GREEN}최소 동시 사용자:${NC} $MIN_VUS 명"
    echo -e "${RED}최대 동시 사용자:${NC} $MAX_VUS 명"
    
    # 부하 수준별 응답시간 분석 (근사치)
    echo ""
    echo -e "${YELLOW}부하 수준별 응답시간 분석:${NC}"
    
    # 전체 응답시간을 3구간으로 나눠서 분석
    TOTAL_DURATION_LINES=$(wc -l < "$DURATION_FILE")
    EARLY_THIRD=$(echo "$TOTAL_DURATION_LINES / 3" | bc)
    MIDDLE_THIRD=$(echo "$TOTAL_DURATION_LINES * 2 / 3" | bc)
    
    EARLY_AVG=$(head -n "$EARLY_THIRD" "$DURATION_FILE" | awk '{sum+=$1} END {printf "%.2f", sum/NR}' 2>/dev/null || echo "0")
    MIDDLE_AVG=$(sed -n "${EARLY_THIRD},${MIDDLE_THIRD}p" "$DURATION_FILE" | awk '{sum+=$1} END {printf "%.2f", sum/NR}' 2>/dev/null || echo "0")
    LATE_AVG=$(tail -n "+$(echo "$MIDDLE_THIRD + 1" | bc)" "$DURATION_FILE" | awk '{sum+=$1} END {printf "%.2f", sum/NR}' 2>/dev/null || echo "0")
    
    printf "${GREEN}초기 (낮은 부하)${NC}: 평균 %.2f ms\n" "$EARLY_AVG"
    printf "${YELLOW}중기 (보통 부하)${NC}: 평균 %.2f ms\n" "$MIDDLE_AVG"  
    printf "${RED}후기 (높은 부하)${NC}: 평균 %.2f ms\n" "$LATE_AVG"
    
    echo ""
    echo -e "${BLUE}💡 부하별 성능 해석:${NC}"
    if (( $(echo "$LATE_AVG > $EARLY_AVG * 2" | bc -l 2>/dev/null || echo "0") )); then
        echo -e "${RED}⚠️  부하 증가시 응답시간이 크게 증가함 - 스케일링 필요${NC}"
    elif (( $(echo "$LATE_AVG > $EARLY_AVG * 1.5" | bc -l 2>/dev/null || echo "0") )); then
        echo -e "${YELLOW}📊 부하 증가시 응답시간이 다소 증가 - 모니터링 필요${NC}"
    else
        echo -e "${GREEN}✅ 부하 증가에도 안정적인 응답시간 유지${NC}"
    fi
else
    echo -e "${YELLOW}동시 사용자 데이터가 충분하지 않습니다${NC}"
fi

# 임시 파일 정리
rm -f "$VUS_FILE" "$TIMELINE_FILE" 2>/dev/null

# 테스트된 API 엔드포인트 분석
echo ""
echo -e "${PURPLE}🌐 테스트된 API 엔드포인트${NC}"
echo "=================================================="

# 각 엔드포인트별 요청 수 분석
echo -e "${YELLOW}테스트된 엔드포인트별 요청 분포:${NC}"

# 주요 API 엔드포인트들 추출 및 카운트
TEMP_ENDPOINTS=$(mktemp)
grep '"url":' "$RESULT_FILE" | sed 's/.*"url":"\([^"]*\)".*/\1/' | \
    sed -E 's#https?://[^/]+/##' | \
    sort | uniq -c | sort -rn > "$TEMP_ENDPOINTS"

echo ""
echo -e "${BLUE}📋 API 엔드포인트 상세 분석:${NC}"
printf "${GREEN}%-8s %-50s %-20s${NC}\n" "요청수" "엔드포인트" "기능 설명"
echo "─────────────────────────────────────────────────────────────────────────────────"

while read count endpoint; do
    case "$endpoint" in
        "/api/v1/auths/")
            DESCRIPTION="👤 현재 세션 사용자 정보"
            ;;
        "/api/v1/auths/signin")
            DESCRIPTION="🔑 사용자 로그인 (인증 토큰 발급)"
            ;;
        "/api/v1/users/me")
            DESCRIPTION="👤 현재 사용자 프로필 조회"
            ;;
        "/api/v1/users/")
            DESCRIPTION="👥 전체 사용자 목록 (관리자 전용)"
            ;;
        "/api/v1/chats/")
            DESCRIPTION="💬 사용자의 채팅 목록 조회"
            ;;
        "/api/v1/models/")
            DESCRIPTION="🤖 사용 가능한 AI 모델 목록"
            ;;
        "/api/models")
            DESCRIPTION="🤖 사용 가능한 AI 모델 목록 (통합)"
            ;;
        "/api/v1/prompts/")
            DESCRIPTION="📝 프롬프트 템플릿 목록"
            ;;
        "/api/v1/documents/")
            DESCRIPTION="📄 문서 목록 (지식베이스)"
            ;;
        "/api/v1/knowledge/")
            DESCRIPTION="🧠 지식베이스 목록"
            ;;
        "/api/v1/tools/")
            DESCRIPTION="🔧 사용 가능한 도구 목록"
            ;;
        "/api/v1/files/")
            DESCRIPTION="📎 파일 업로드"
            ;;
        "/health")
            DESCRIPTION="💚 서버 상태 확인"
            ;;
        *)
            DESCRIPTION="🌐 기타 API 엔드포인트"
            ;;
    esac
    
    # 색상 지정 (요청 수에 따라)
    if [ $count -gt 10000 ]; then
        COLOR="${RED}"
    elif [ $count -gt 1000 ]; then
        COLOR="${YELLOW}"
    else
        COLOR="${GREEN}"
    fi
    
    printf "${COLOR}%-8d${NC} %-50s ${BLUE}%s${NC}\n" "$count" "$endpoint" "$DESCRIPTION"
done < "$TEMP_ENDPOINTS"

echo ""
echo -e "${PURPLE}📊 API 카테고리별 요청 분석:${NC}"

# 카테고리별 분석
AUTH_REQS=$(grep '"url":".*auths' "$RESULT_FILE" | wc -l)
USER_REQS=$(grep '"url":".*users' "$RESULT_FILE" | wc -l)
CHAT_REQS=$(grep '"url":".*chats' "$RESULT_FILE" | wc -l)
MODEL_REQS=$(grep '"url":".*models' "$RESULT_FILE" | wc -l)
CONTENT_REQS=$(echo "$(grep '"url":".*documents' "$RESULT_FILE" | wc -l) + $(grep '"url":".*knowledge' "$RESULT_FILE" | wc -l) + $(grep '"url":".*prompts' "$RESULT_FILE" | wc -l)" | bc)
TOOL_REQS=$(grep '"url":".*tools' "$RESULT_FILE" | wc -l)
FILE_REQS=$(grep '"url":".*files' "$RESULT_FILE" | wc -l)

if [ $AUTH_REQS -gt 0 ]; then
    printf "${GREEN}🔑 인증 관련:${NC} %'d 회 (로그인, 토큰 관리)\n" "$AUTH_REQS"
fi
if [ $USER_REQS -gt 0 ]; then
    printf "${BLUE}👤 사용자 관련:${NC} %'d 회 (프로필, 사용자 목록)\n" "$USER_REQS"
fi
if [ $CHAT_REQS -gt 0 ]; then
    printf "${PURPLE}💬 채팅 관련:${NC} %'d 회 (채팅 목록 - 메타데이터만)\n" "$CHAT_REQS"
fi
if [ $MODEL_REQS -gt 0 ]; then
    printf "${YELLOW}🤖 AI 모델 관련:${NC} %'d 회 (모델 목록 조회)\n" "$MODEL_REQS"
fi
if [ $CONTENT_REQS -gt 0 ]; then
    printf "${RED}📚 콘텐츠 관련:${NC} %'d 회 (문서, 지식베이스, 프롬프트)\n" "$CONTENT_REQS"
fi
if [ $TOOL_REQS -gt 0 ]; then
    printf "${PURPLE}🔧 도구 관련:${NC} %'d 회 (도구 목록 조회)\n" "$TOOL_REQS"
fi
if [ $FILE_REQS -gt 0 ]; then
    printf "${GREEN}📎 파일 관련:${NC} %'d 회 (파일 업로드)\n" "$FILE_REQS"
fi

# 커스텀 메트릭
echo ""
echo -e "${PURPLE}📈 테스트 메트릭 요약${NC}"
echo "=================================================="

AUTH_COUNT=$(grep '"metric":"auth_operations_total"' "$RESULT_FILE" | wc -l)
API_COUNT=$(grep '"metric":"api_operations_total"' "$RESULT_FILE" | wc -l)
CHAT_COUNT=$(grep '"metric":"chat_operations_total"' "$RESULT_FILE" | wc -l)

if [ $AUTH_COUNT -gt 0 ]; then
    echo -e "${YELLOW}인증 작업:${NC} $AUTH_COUNT 회 (로그인/토큰 갱신)"
fi
if [ $API_COUNT -gt 0 ]; then
    echo -e "${YELLOW}API 작업:${NC} $API_COUNT 회 (일반 API 호출 - 채팅 목록 포함)"  
fi
# 실제 채팅 작업 판단 (AI 메시지 관련 메트릭이 있는지 확인)
MSGS_SENT_COUNT=$(grep '"metric":"messages_sent_total"' "$RESULT_FILE" | wc -l)
AI_RESPONSE_COUNT=$(grep '"metric":"ai_response_duration_ms"' "$RESULT_FILE" | wc -l)

if [ $CHAT_COUNT -gt 0 ]; then
    if [ $MSGS_SENT_COUNT -gt 0 ] || [ $AI_RESPONSE_COUNT -gt 0 ]; then
        echo -e "${YELLOW}실제 채팅 작업:${NC} $CHAT_COUNT 회 (AI 대화, 채팅방 생성 등)"
        REAL_CHAT_DETECTED=true
    else
        echo -e "${YELLOW}채팅 메트릭:${NC} $CHAT_COUNT 회 (⚠️ 이전 테스트 결과 - 채팅 목록 조회만)"
        REAL_CHAT_DETECTED=false
    fi
fi

echo ""
echo -e "${BLUE}💡 메트릭 설명:${NC}"
echo -e "${GREEN}• 인증 작업${NC}: 로그인 및 토큰 관리"
echo -e "${YELLOW}• API 작업${NC}: 데이터 조회 (목록, 프로필 등)"
if [ "$REAL_CHAT_DETECTED" = "true" ]; then
    echo -e "${RED}• 실제 채팅 작업${NC}: AI 모델과의 실제 대화 (리소스 집약적)"
else
    echo -e "${BLUE}• 채팅 메트릭 (참고)${NC}: 이전 버전 결과 - 실제로는 채팅 목록 조회만 수행"
    echo -e "${PURPLE}• 현재 스크립트 버전${NC}: 채팅 목록은 API 작업으로 분류됨"
fi

# 임시 파일 정리
rm -f "$TEMP_ENDPOINTS" 2>/dev/null

# 성능 평가
echo ""
echo -e "${PURPLE}🎯 성능 평가${NC}"
echo "=================================================="

if (( $(echo "$P95_DURATION < 500" | bc -l 2>/dev/null || echo "0") )); then
    echo -e "${GREEN}✅ 95% 응답시간이 우수합니다 (< 500ms)${NC}"
elif (( $(echo "$P95_DURATION < 1000" | bc -l 2>/dev/null || echo "0") )); then
    echo -e "${YELLOW}⚠️  95% 응답시간이 양호합니다 (< 1000ms)${NC}"
else
    echo -e "${RED}❌ 95% 응답시간이 개선이 필요합니다 (> 1000ms)${NC}"
fi

if (( $(echo "$FAILURE_RATE < 1" | bc -l 2>/dev/null || echo "0") )); then
    echo -e "${GREEN}✅ 에러율이 우수합니다 (< 1%)${NC}"
elif (( $(echo "$FAILURE_RATE < 5" | bc -l 2>/dev/null || echo "0") )); then
    echo -e "${YELLOW}⚠️  에러율이 양호합니다 (< 5%)${NC}"
else
    echo -e "${RED}❌ 에러율이 높습니다 (> 5%)${NC}"
fi

# 정리
rm -f "$DURATION_FILE" 2>/dev/null

echo ""
echo -e "${GREEN}분석 완료! 🎉${NC}"
