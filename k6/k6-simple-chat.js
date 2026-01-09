/*
  간단한 채팅 테스트 - Open WebUI

  사전 정의된 계정으로 로그인하여 실제 AI와 채팅만 테스트합니다.
  다른 기능 확인 없이 순수하게 채팅 기능만 검증합니다.

  Environment variables:
  - BASE_URL: 대상 서버 URL (default: http://localhost:8088)
  - TEST_EMAIL: 사용자 이메일 (default: test@mail.com)
  - TEST_PASSWORD: 사용자 비밀번호 (default: 1234)
  - MODEL_NAME: 사용할 모델 이름 (default: individual_mode)
  - MESSAGE_COUNT: 전송할 메시지 개수 (default: 3)
  - VUS: 동시 사용자 수 (default: 1)
  - DURATION: 테스트 시간 (default: 60s)
*/

import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate, Counter, Trend } from 'k6/metrics';

// 전역 변수로 통계 추적
let globalStats = {
  sent: 0,
  success: 0,
  failed: 0,
  received: 0
};

// 커스텀 메트릭
const errorRate = new Rate('errors');
const messagesSent = new Counter('messages_sent_total');
const messagesReceived = new Counter('messages_received_total');
const messagesSuccess = new Counter('messages_success_total');
const messagesFailed = new Counter('messages_failed_total');
const aiResponseTime = new Trend('ai_response_time_ms');

// 에러 코드별 카운터
const error400 = new Counter('error_400_bad_request');
const error401 = new Counter('error_401_unauthorized');
const error403 = new Counter('error_403_forbidden');
const error404 = new Counter('error_404_not_found');
const error429 = new Counter('error_429_rate_limit');
const error500 = new Counter('error_500_internal');
const error502 = new Counter('error_502_bad_gateway');
const error503 = new Counter('error_503_unavailable');
const errorTimeout = new Counter('error_timeout');
const errorOther = new Counter('error_other');

// 테스트 설정
export const options = {
  vus: parseInt(__ENV.VUS || '1', 10),
  iterations: 1,  // 정확히 1번만 실행 (duration 대신 사용)
  thresholds: {
    http_req_duration: ['p(95)<30000'],  // AI 응답 시간 고려해서 30초로 조정
    http_req_failed: ['rate<0.1'],
    errors: ['rate<0.1'],
  },
};

// 환경 변수
const BASE_URL = __ENV.BASE_URL || 'http://localhost:8088';
const TEST_EMAIL = __ENV.TEST_EMAIL || 'test@mail.com';
const TEST_PASSWORD = __ENV.TEST_PASSWORD || '1234';
const MODEL_NAME = __ENV.MODEL_NAME || 'test_workspace';
const MESSAGE_COUNT = parseInt(__ENV.MESSAGE_COUNT || '3', 10);

// 테스트 메시지 목록
const TEST_MESSAGES = [
  "안녕하세요! 오늘 날씨가 어떤가요?",
  "파이썬에서 리스트 컴프리헨션을 설명해주세요.",
  "간단한 파스타 레시피를 알려주세요.",
  "REST API와 GraphQL의 차이점은 무엇인가요?",
  "효과적인 코드 리뷰 방법을 알려주세요.",
  "데이터베이스 인덱스는 언제 사용하나요?",
  "마이크로서비스 아키텍처의 장단점을 설명해주세요.",
  "Git rebase와 merge의 차이는 무엇인가요?",
  "도커와 쿠버네티스의 관계를 설명해주세요.",
  "테스트 주도 개발(TDD)에 대해 설명해주세요."
];

let authToken = null;

// 헬퍼 함수
function jsonHeaders() {
  return {
    headers: {
      'Content-Type': 'application/json',
      ...(authToken ? { Authorization: `Bearer ${authToken}` } : {}),
    }
  };
}

function safeJson(res) {
  try {
    return res.json();
  } catch (_) {
    return null;
  }
}

function getRandomMessage() {
  return TEST_MESSAGES[Math.floor(Math.random() * TEST_MESSAGES.length)];
}

// 로그인 함수
function login() {
  console.log(`Attempting login: ${TEST_EMAIL}`);

  const loginRes = http.post(
    `${BASE_URL}/api/v1/auths/signin`,
    JSON.stringify({
      email: TEST_EMAIL,
      password: TEST_PASSWORD
    }),
    jsonHeaders()
  );

  if (loginRes.status === 200) {
    const body = safeJson(loginRes);
    if (body && body.token) {
      authToken = body.token;
      console.log('✅ Login successful');
      return true;
    }
  }

  console.log(`❌ Login failed: ${loginRes.status}`);
  errorRate.add(1);
  return false;
}

// 채팅방 생성
function createChat() {
  const chatPayload = {
    chat: {
      title: `Simple Chat Test - ${Date.now()}`,
      models: [MODEL_NAME],
      messages: []
    }
  };

  const createRes = http.post(
    `${BASE_URL}/api/v1/chats/new`,
    JSON.stringify(chatPayload),
    {
      ...jsonHeaders(),
      timeout: '10s'
    }
  );

  if (createRes.status === 200) {
    const chatData = safeJson(createRes);
    if (chatData && chatData.id) {
      console.log(`✅ Chat created: ${chatData.id}`);
      return chatData.id;
    }
  }

  console.log(`❌ Chat creation failed: ${createRes.status}`);
  errorRate.add(1);
  return null;
}

// 에러 코드 추적 함수
function trackErrorCode(status) {
  switch(status) {
    case 400:
      error400.add(1);
      return 'Bad Request';
    case 401:
      error401.add(1);
      return 'Unauthorized';
    case 403:
      error403.add(1);
      return 'Forbidden';
    case 404:
      error404.add(1);
      return 'Not Found';
    case 429:
      error429.add(1);
      return 'Rate Limited';
    case 500:
      error500.add(1);
      return 'Internal Server Error';
    case 502:
      error502.add(1);
      return 'Bad Gateway';
    case 503:
      error503.add(1);
      return 'Service Unavailable';
    case 0:
      errorTimeout.add(1);
      return 'Timeout/Network Error';
    default:
      errorOther.add(1);
      return `Other Error (${status})`;
  }
}

// AI와 대화
function sendMessage(chatId, messageNumber) {
  const userMessage = getRandomMessage();
  console.log(`📤 Message ${messageNumber}: ${userMessage.substring(0, 40)}...`);

  const messagePayload = {
    model: MODEL_NAME,
    messages: [
      {
        role: 'user',
        content: userMessage
      }
    ],
    options: {},
    stream: false  // 스트리밍 비활성화 (단순 테스트)
  };

  const startTime = Date.now();
  messagesSent.add(1);  // 전송 시도 카운트
  globalStats.sent++;   // 전역 변수 업데이트

  const messageRes = http.post(
    `${BASE_URL}/api/chat/completions`,
    JSON.stringify(messagePayload),
    {
      ...jsonHeaders(),
      timeout: '30s'
    }
  );

  const responseTime = Date.now() - startTime;
  aiResponseTime.add(responseTime);

  if (messageRes.status === 200) {
    const response = safeJson(messageRes);

    if (response && response.choices && response.choices[0]) {
      messagesReceived.add(1);
      messagesSuccess.add(1);
      globalStats.received++;  // 전역 변수 업데이트
      globalStats.success++;   // 전역 변수 업데이트
      const aiResponse = response.choices[0].message.content;
      console.log(`📥 AI Response: ${aiResponse.substring(0, 50)}...`);
      console.log(`   ⏱️  Response time: ${responseTime}ms`);
      return { success: true, status: 200, responseTime };
    } else {
      // 200 응답이지만 내용이 없는 경우
      messagesFailed.add(1);
      globalStats.failed++;  // 전역 변수 업데이트
      console.log(`❌ Empty response despite 200 status`);
      return { success: false, status: 200, error: 'Empty Response', responseTime };
    }
  }

  // 실패 케이스
  messagesFailed.add(1);
  globalStats.failed++;  // 전역 변수 업데이트
  errorRate.add(1);
  const errorType = trackErrorCode(messageRes.status);
  console.log(`❌ Message failed: ${messageRes.status} - ${errorType}`);

  // 에러 상세 정보 출력 (있는 경우)
  if (messageRes.body) {
    const errorBody = messageRes.body.substring(0, 100);
    console.log(`   Error details: ${errorBody}`);
  }

  return { success: false, status: messageRes.status, error: errorType, responseTime };
}

// 메인 테스트 함수
export default function () {
  console.log('\n========================================');
  console.log('테스트 시작 - MESSAGE_COUNT:', MESSAGE_COUNT);
  console.log('========================================\n');

  // 1. 로그인 (최초 1회만)
  if (!authToken) {
    if (!login()) {
      console.log('Authentication failed, stopping test');
      return;
    }
    sleep(1);
  }

  // 2. 채팅방 생성
  const chatId = createChat();
  if (!chatId) {
    console.log('Chat creation failed, skipping messages');
    return;
  }
  sleep(1);

  // 3. 메시지 전송
  let successCount = 0;
  let failCount = 0;
  const sessionErrors = {};  // 이 세션의 에러 추적

  console.log(`\n📝 메시지 전송 시작 (총 ${MESSAGE_COUNT}개)`);

  for (let i = 1; i <= MESSAGE_COUNT; i++) {
    console.log(`\n--- Message ${i}/${MESSAGE_COUNT} ---`);

    const result = sendMessage(chatId, i);

    if (result.success) {
      successCount++;
    } else {
      failCount++;
      // 에러 유형별 카운트
      const errorKey = `${result.status}_${result.error}`;
      sessionErrors[errorKey] = (sessionErrors[errorKey] || 0) + 1;
    }

    // 메시지 사이 대기 (AI 부하 방지)
    if (i < MESSAGE_COUNT) {
      const waitTime = 3 + Math.random() * 2;  // 3-5초 대기
      console.log(`⏳ Waiting ${waitTime.toFixed(1)}s before next message...`);
      sleep(waitTime);
    }
  }

  // 4. 세션 요약
  console.log('\n=== Session Summary ===');
  console.log(`✅ Success: ${successCount}/${MESSAGE_COUNT}`);
  if (failCount > 0) {
    console.log(`❌ Failed: ${failCount}/${MESSAGE_COUNT}`);
    if (Object.keys(sessionErrors).length > 0) {
      console.log('Error breakdown:');
      for (const [error, count] of Object.entries(sessionErrors)) {
        console.log(`  • ${error}: ${count} times`);
      }
    }
  }
  console.log('=====================\n');

  // 세션 간 대기
  sleep(2);
}

// 테스트 종료 시 요약
export function teardown(data) {
  console.log('\n');
  console.log('=========================================');
  console.log('         채팅 테스트 완료');
  console.log('=========================================');

  // teardown에서는 globalStats가 초기화되므로 실행 결과만 표시
  console.log(`\n📊 메시지 전송 통계:`);
  console.log('   k6 TOTAL RESULTS 섹션을 확인하세요');
  console.log('   - messages_sent_total: 전송 시도');
  console.log('   - messages_success_total: 성공');
  console.log('   - messages_failed_total: 실패');
  console.log('   - messages_received_total: AI 응답 수신');

  console.log('\n📋 테스트 완료!');
  console.log('   상세 결과는 위의 Session Summary와');
  console.log('   TOTAL RESULTS 섹션을 참고하세요.');

  console.log('=========================================\n');
}