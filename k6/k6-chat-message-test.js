/*
  워크스페이스 기반 채팅 테스트 - Open WebUI
  
  실제 워크스페이스 환경에서 AI 모델(기본/pipe function 포함)과의 채팅을 테스트합니다.
  워크스페이스에 설정된 모델, 프롬프트, 도구 등을 활용한 통합 테스트입니다.

  Environment variables:
  - BASE_URL: target base URL (default: http://localhost:8088)
  - TEST_EMAIL: 기존 사용자 이메일 (REQUIRED - 새 계정 생성 안함)
  - TEST_PASSWORD: 기존 사용자 비밀번호 (REQUIRED)
  - WORKSPACE_ID: 사용할 워크스페이스 ID (REQUIRED - 특정 워크스페이스 지정)
  - SEND_MESSAGES: "true"로 설정시 실제 메시지 전송 (default: false)
  - MESSAGE_DELAY: 메시지 간 대기 시간 (초, default: 3)
  - USE_WORKSPACE_MODELS: 워크스페이스 모델 사용 여부 (default: true)
*/

import http from 'k6/http';
import { check, sleep, group } from 'k6';
import { Rate, Counter } from 'k6/metrics';
import ws from 'k6/ws';

// 커스텀 메트릭
const errorRate = new Rate('errors');
const messagesSent = new Counter('messages_sent_total');
const messagesReceived = new Counter('messages_received_total');
const aiResponseTime = new Counter('ai_response_duration_ms');

// Load test configuration
const vus = parseInt(__ENV.VUS || '5', 10);
const duration = __ENV.DURATION || '12m';
const testType = __ENV.TEST_TYPE || 'load';

// Test type configurations
let opt = {};

switch(testType) {
  case 'simple':
    // Simple constant load
    opt = {
      vus: vus,
      duration: duration,
      thresholds: {
        http_req_duration: ['p(95)<5000'],
        http_req_failed: ['rate<0.1'],
        errors: ['rate<0.1'],
      },
    };
    break;

  case 'spike':
    // Spike test - sudden load increase
    opt = {
      stages: [
        { duration: '2m', target: Math.ceil(vus * 0.3) },
        { duration: '1m', target: vus * 2 },
        { duration: '3m', target: vus * 2 },
        { duration: '1m', target: Math.ceil(vus * 0.3) },
        { duration: '3m', target: Math.ceil(vus * 0.3) },
      ],
      thresholds: {
        http_req_duration: ['p(95)<8000'],
        http_req_failed: ['rate<0.2'],
        errors: ['rate<0.2'],
      },
    };
    break;

  case 'stress':
    // Stress test - find breaking point
    opt = {
      stages: [
        { duration: '2m', target: 5 },
        { duration: '3m', target: 10 },
        { duration: '3m', target: 20 },
        { duration: '3m', target: 30 },
        { duration: '10m', target: 30 },
        { duration: '3m', target: 0 },
      ],
      thresholds: {
        http_req_duration: ['p(99)<10000'],
        http_req_failed: ['rate<0.3'],
        errors: ['rate<0.3'],
      },
    };
    break;

  case 'volume':
    // Volume test - long duration stability
    opt = {
      stages: [
        { duration: '5m', target: Math.ceil(vus * 0.8) },
        { duration: '30m', target: Math.ceil(vus * 0.8) },
        { duration: '5m', target: 0 },
      ],
      thresholds: {
        http_req_duration: ['p(95)<5000'],
        http_req_failed: ['rate<0.05'],
        errors: ['rate<0.05'],
      },
    };
    break;

  default: // 'load'
    // Standard load test - gradual increase
    opt = {
      stages: [
        { duration: '1m', target: Math.ceil(vus * 0.3) },
        { duration: '3m', target: Math.ceil(vus * 0.3) },
        { duration: '1m', target: Math.ceil(vus * 0.6) },
        { duration: '3m', target: Math.ceil(vus * 0.6) },
        { duration: '1m', target: vus },
        { duration: '3m', target: vus },
        { duration: '2m', target: 0 },
      ],
      thresholds: {
        http_req_duration: ['p(95)<5000'],
        http_req_failed: ['rate<0.1'],
        errors: ['rate<0.1'],
      },
    };
}

export const options = opt;

// 환경 변수 설정
const BASE_URL = __ENV.BASE_URL || 'http://localhost:8088';
const TEST_EMAIL = __ENV.TEST_EMAIL || 'test@mail.com';
const TEST_PASSWORD = __ENV.TEST_PASSWORD || '1234';
const WORKSPACE_ID = __ENV.WORKSPACE_ID || 'test_workspace'; // 선택적: 특정 워크스페이스 지정
const SEND_MESSAGES = (__ENV.SEND_MESSAGES || 'true').toLowerCase() === 'true';
const MESSAGE_DELAY = parseInt(__ENV.MESSAGE_DELAY || '30', 10);
const USE_WORKSPACE_MODELS = (__ENV.USE_WORKSPACE_MODELS || 'true').toLowerCase() === 'true';

// 테스트 메시지 샘플
const TEST_MESSAGES = [
  "안녕하세요! 오늘 날씨는 어떤가요?",
  "파이썬에서 리스트와 튜플의 차이점을 설명해 주세요.",
  "간단한 레시피 하나 추천해 주실 수 있나요?",
  "Open WebUI의 주요 기능에 대해 알려주세요.",
  "머신러닝과 딥러닝의 차이점은 무엇인가요?",
  "효과적인 시간 관리 방법을 알려주세요.",
  "데이터베이스 정규화란 무엇인가요?",
  "REST API 설계 원칙에 대해 설명해 주세요.",
  "클라우드 컴퓨팅의 장점은 무엇인가요?",
  "좋은 코드를 작성하는 팁을 알려주세요."
];

let authToken;

// 헬퍼 함수들
function jsonHeaders(extra = {}) {
  return {
    headers: {
      'Content-Type': 'application/json',
      ...(authToken ? { Authorization: `Bearer ${authToken}` } : {}),
      ...extra,
    }
  };
}

function ensureAuth() {
  if (authToken) return authToken;

  // 기존 계정으로만 로그인 (회원가입 비활성화)
  if (!TEST_EMAIL || !TEST_PASSWORD) {
    console.log('ERROR: TEST_EMAIL and TEST_PASSWORD are required for existing user login');
    return null;
  }

  const signinPayload = {
    email: TEST_EMAIL,
    password: TEST_PASSWORD
  };

  console.log(`Attempting login with existing user: ${TEST_EMAIL}`);
  const signinRes = http.post(`${BASE_URL}/api/v1/auths/signin`, JSON.stringify(signinPayload), jsonHeaders());
  
  if (signinRes.status === 200) {
    const body = signinRes.json();
    authToken = body.token;
    console.log(`Successfully logged in as: ${TEST_EMAIL}`);
    return authToken;
  } else {
    console.log(`Login failed for user: ${TEST_EMAIL}. Status: ${signinRes.status}`);
    return null;
  }
}

function randomMessage() {
  return TEST_MESSAGES[Math.floor(Math.random() * TEST_MESSAGES.length)];
}

function safeJson(res) {
  try {
    return res.json();
  } catch (_) {
    return null;
  }
}

// 워크스페이스 목록 조회
function getWorkspaces() {
  const res = http.get(`${BASE_URL}/api/v1/workspaces/`, jsonHeaders());
  
  if (check(res, { 'workspaces loaded': (r) => r.status === 200 })) {
    return safeJson(res);
  }
  
  return [];
}

// 워크스페이스의 사용 가능한 모델 조회
function getWorkspaceModels(workspaceId = null) {
  let url = `${BASE_URL}/api/v1/models/`;
  if (workspaceId) {
    url += `?workspace=${workspaceId}`;
  }
  
  const res = http.get(url, jsonHeaders());
  
  if (check(res, { 'workspace models loaded': (r) => r.status === 200 })) {
    const models = safeJson(res);
    return models || [];
  }
  
  return [];
}

// 워크스페이스의 프롬프트 조회
function getWorkspacePrompts(workspaceId = null) {
  let url = `${BASE_URL}/api/v1/prompts/`;
  if (workspaceId) {
    url += `?workspace=${workspaceId}`;
  }
  
  const res = http.get(url, jsonHeaders());
  
  if (check(res, { 'workspace prompts loaded': (r) => r.status === 200 || r.status === 404 })) {
    const prompts = safeJson(res);
    return prompts || [];
  }
  
  return [];
}

// 채팅 생성 및 메시지 전송 테스트 - individual_mode 모델 사용
function testWorkspaceChat() {
  group('chat-conversation', () => {
    let availableModels = [];

    console.log('Starting chat creation test with individual_mode model');
    
    // individual_mode 모델 사용
    let selectedModels = ['individual_mode'];
    console.log(`Using individual_mode model: ${selectedModels[0]}`);
    
    // 3. 채팅 생성 - workspace_id 제거
    const chatPayload = {
      chat: {
        title: `K6 Chat - ${Date.now()}`,
        models: selectedModels,
        messages: []
      }
    };

    const createRes = http.post(
      `${BASE_URL}/api/v1/chats/new`,
      JSON.stringify(chatPayload),
      {
        ...jsonHeaders(),
        timeout: '10s'  // 10초 타임아웃 설정
      }
    );

    const chatCreateSuccess = check(createRes, {
      'chat created': (r) => r.status === 200,
      'chat create timeout': (r) => r.status !== 0  // 타임아웃이 아님
    });

    if (!chatCreateSuccess) {
      console.log(`Chat creation failed: ${createRes.status} - ${createRes.body?.substring(0, 100)}`);
      errorRate.add(1);
      return;
    }

    const chatData = safeJson(createRes);
    if (!chatData || !chatData.id) {
      errorRate.add(1);
      return;
    }

    const chatId = chatData.id;
    console.log(`Chat created: ${chatId}`);

    if (!SEND_MESSAGES) {
      console.log('SEND_MESSAGES is false, skipping message sending');
      return;
    }

    // 2. 실제 메시지 전송
    for (let i = 0; i < 1; i++) { // 테스트용으로 1개 메시지만 전송
      const userMessage = randomMessage();
      console.log(`Sending message ${i + 1}: ${userMessage.substring(0, 30)}...`);
      
      const messagePayload = {
        model: selectedModels[0] || 'dp',
        messages: [
          {
            role: 'user',
            content: userMessage
          }
        ],
        options: {},
        format: '',
        keep_alive: null,
        stream: false // 스트리밍 비활성화로 테스트 단순화
      };

      const startTime = Date.now();
      
      // OpenAI API 호환 엔드포인트 사용 (올바른 경로: /api/chat/completions)
      const messageRes = http.post(
        `${BASE_URL}/api/chat/completions`, 
        JSON.stringify(messagePayload), 
        {
          ...jsonHeaders(),
          timeout: '30s' // AI 응답 대기시간 30초
        }
      );

      const responseTime = Date.now() - startTime;
      aiResponseTime.add(responseTime);
      
      const messageSuccess = check(messageRes, {
        'message sent successfully': (r) => r.status === 200,
        'response time < 20s': () => responseTime < 20000,
      });

      if (messageSuccess) {
        messagesSent.add(1);
        const response = safeJson(messageRes);
        if (response && response.choices && response.choices[0]) {
          messagesReceived.add(1);
          console.log(`AI Response: ${response.choices[0].message.content.substring(0, 50)}...`);
        }
      } else {
        errorRate.add(1);
        console.log(`Message failed: ${messageRes.status} - ${messageRes.body.substring(0, 100)}`);
      }

      // 메시지 간 대기 (단축)
      sleep(Math.min(MESSAGE_DELAY, 5)); // 최대 5초로 제한
    }

    // 3. 채팅 저장 확인
    const chatCheckRes = http.get(`${BASE_URL}/api/v1/chats/${chatId}`, jsonHeaders());
    check(chatCheckRes, {
      'chat history retrieved': (r) => r.status === 200,
    }) || errorRate.add(1);
  });
}

// 기존 채팅 목록 테스트
function testChatList() {
  group('chats:list', () => {
    const res = http.get(`${BASE_URL}/api/v1/chats/`, jsonHeaders());
    const success = check(res, {
      'chats list 200': (r) => r.status === 200,
    });
    if (!success) errorRate.add(1);
  });
}

// 메인 테스트 함수
export default function () {
  // 인증 확인
  const token = ensureAuth();
  if (!token) {
    console.log('Authentication failed, skipping chat tests');
    errorRate.add(1);
    return;
  }

  // 시나리오 선택
  const scenario = Math.random();
  
  if (scenario < 0.3) {
    // 30% - 채팅 목록만 조회 (가벼운 작업)
    testChatList();
    sleep(1);
  } else {
    // 70% - 실제 채팅 대화 (AI 메시지 전송)
    testWorkspaceChat();
    sleep(2); // AI 처리 시간 고려하여 적당한 대기
  }
}

export function teardown() {
  console.log('=== 채팅 테스트 결과 ===');
  console.log(`전송된 메시지: ${messagesSent.count}`);
  console.log(`받은 응답: ${messagesReceived.count}`);
  console.log(`Test type: ${testType}`);
  console.log(`Target users: ${vus}`);
  console.log(`Duration: ${duration}`);

  if (SEND_MESSAGES) {
    console.log('실제 AI 대화 테스트가 수행되었습니다.');
  } else {
    console.log('SEND_MESSAGES=false이므로 메시지 전송은 건너뛰었습니다.');
  }
}
