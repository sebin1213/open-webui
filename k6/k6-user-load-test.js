/*
  Open WebUI User Load Test Script - Regular User Only
  
  일반 사용자 계정으로만 접근 가능한 API 엔드포인트 테스트
  관리자 권한이 필요한 API는 제외하고 안전한 테스트만 수행
  
  Environment variables:
  - BASE_URL: target URL (default: http://localhost:8088)
  - EMAIL: existing user email (default: test@mail.com)
  - PASSWORD: existing user password (default: 1234)
  - VUS: virtual users (default: 10)
  - DURATION: test duration (default: 10m)
  - TEST_TYPE: load test type (load, spike, stress, volume, simple)
  - TEST_FILE_UPLOAD: enable file upload tests (default: false)

  Tested endpoints (user-safe only, verified):
  - Authentication (signin) - POST /api/v1/auths/signin
  - Current user info - GET /api/v1/auths/ (NO admin APIs)
  - Chat listing - GET /api/v1/chats/ (user's own)
  - Model listing - GET /api/models (available models)
  - Document/Knowledge - GET /api/v1/documents/, /api/v1/knowledge/
  - Prompts - GET /api/v1/prompts/ (user accessible)
  - Tools - GET /api/v1/tools/ (user accessible)
  - File upload - POST /api/v1/files/ (optional, user files)
*/

import http from 'k6/http';
import { check, sleep, group } from 'k6';
import { Rate, Counter } from 'k6/metrics';

// Custom metrics
const errorRate = new Rate('errors');
const chatOperations = new Counter('chat_operations_total');
const authOperations = new Counter('auth_operations_total');
const fileOperations = new Counter('file_operations_total');
const apiOperations = new Counter('api_operations_total');

// Configuration
const BASE_URL = __ENV.BASE_URL || 'http://localhost:8088';
const AUTH_TOKEN_ENV = __ENV.AUTH_TOKEN;
const LOGIN_EMAIL = __ENV.EMAIL || 'test@mail.com';
const LOGIN_PASSWORD = __ENV.PASSWORD || '1234';
const TEST_FILE_UPLOAD = (__ENV.TEST_FILE_UPLOAD || 'false').toLowerCase() === 'true';

// Load test configuration
const vus = parseInt(__ENV.VUS || '10', 10);
const duration = __ENV.DURATION || '10m';
const rps = parseInt(__ENV.RPS || '0', 10);
const testType = __ENV.TEST_TYPE || 'load';

// Test type configurations
let opt = {};

if (rps > 0) {
  // Constant arrival rate scenario
  opt = {
    scenarios: {
      constant_rate: {
        executor: 'constant-arrival-rate',
        rate: rps,
        timeUnit: '1s', 
        duration: duration,
        preAllocatedVUs: Math.max(vus, Math.ceil(rps * 2)),
        maxVUs: Math.max(vus * 2, Math.ceil(rps * 4)),
      },
    },
    thresholds: {
      http_req_failed: ['rate<0.1'],
      http_req_duration: ['p(95)<1000', 'p(99)<2000'],
      errors: ['rate<0.1'],
    },
  };
} else {
  // Stage-based scenarios
  switch(testType) {
    case 'simple':
      // Simple constant load
      opt = {
        vus: vus,
        duration: duration,
        thresholds: {
          http_req_failed: ['rate<0.01'],
          http_req_duration: ['p(95)<2000', 'p(99)<5000'],
          errors: ['rate<0.01'],
        },
      };
      break;

    case 'spike':
      // Spike test - sudden load increase
      opt = {
        stages: [
          { duration: '2m', target: Math.ceil(vus * 0.3) },  // Normal load
          { duration: '1m', target: vus * 2 },               // Spike (reduced from 3x)
          { duration: '3m', target: vus * 2 },               // Maintain spike  
          { duration: '1m', target: Math.ceil(vus * 0.3) },  // Recovery
          { duration: '3m', target: Math.ceil(vus * 0.3) },  // Stabilize
        ],
        thresholds: {
          http_req_failed: ['rate<0.2'],
          http_req_duration: ['p(95)<2000', 'p(99)<5000'],
          errors: ['rate<0.2'],
        },
      };
      break;
      
    case 'stress':
      // Stress test - find breaking point (reduced scale for user tests)
      opt = {
        stages: [
          { duration: '2m', target: 20 },    // Warm up
          { duration: '3m', target: 50 },    // Moderate load
          { duration: '3m', target: 100 },   // High load
          { duration: '3m', target: 200 },   // Very high load
          { duration: '3m', target: 300 },   // Maximum load
          { duration: '10m', target: 300 },  // Sustain max load
          { duration: '3m', target: 0 },     // Cool down
        ],
        thresholds: {
          http_req_failed: ['rate<0.3'],     // Allow higher error rate
          http_req_duration: ['p(99)<5000'], // Focus on 99th percentile
          errors: ['rate<0.3'],
        },
      };
      break;
      
    case 'volume':
      // Volume test - long duration stability
      opt = {
        stages: [
          { duration: '5m', target: Math.ceil(vus * 1.2) }, // Ramp up (reduced)
          { duration: '30m', target: Math.ceil(vus * 1.2) }, // Long sustained load
          { duration: '5m', target: 0 },                     // Cool down
        ],
        thresholds: {
          http_req_failed: ['rate<0.05'],
          http_req_duration: ['p(95)<1000', 'p(99)<2000'],
          errors: ['rate<0.05'],
        },
      };
      break;
      
    default: // 'load'
      // Standard load test - gradual increase
      opt = {
        stages: [
          { duration: '2m', target: Math.ceil(vus * 0.3) },  // 30% ramp up
          { duration: '5m', target: Math.ceil(vus * 0.3) },  // 30% sustain
          { duration: '2m', target: Math.ceil(vus * 0.6) },  // 60% ramp up
          { duration: '5m', target: Math.ceil(vus * 0.6) },  // 60% sustain
          { duration: '2m', target: vus },                   // 100% ramp up 
          { duration: '5m', target: vus },                   // 100% sustain
          { duration: '5m', target: 0 },                     // Cool down
        ],
        thresholds: {
          http_req_failed: ['rate<0.1'],
          http_req_duration: ['p(95)<1000', 'p(99)<2000'],
          errors: ['rate<0.1'],
        },
      };
  }
}

export const options = opt;

// Helper functions
let authToken;

function jsonHeaders(extra = {}) {
  return {
    headers: {
      'Content-Type': 'application/json',
      ...(authToken ? { Authorization: `Bearer ${authToken}` } : {}),
      ...extra,
    },
  };
}

function formHeaders() {
  return {
    headers: {
      ...(authToken ? { Authorization: `Bearer ${authToken}` } : {}),
    },
  };
}

function safeJson(res) {
  try {
    return res.json();
  } catch (_) {
    return null;
  }
}

function ensureAuth() {
  if (authToken) return authToken;

  // Try existing account login first
  if (LOGIN_EMAIL && LOGIN_PASSWORD) {
    const signinRes = http.post(
      `${BASE_URL}/api/v1/auths/signin`,
      JSON.stringify({ email: LOGIN_EMAIL, password: LOGIN_PASSWORD }),
      jsonHeaders()
    );
    
    if (signinRes.status === 200) {
      const body = safeJson(signinRes);
      if (body && body.token) {
        authToken = body.token;
        authOperations.add(1);
        return authToken;
      }
    }
  }

  // Use pre-set token if available
  if (AUTH_TOKEN_ENV) {
    authToken = AUTH_TOKEN_ENV;
    return authToken;
  }

  console.log('Authentication failed - no valid credentials');
  return null;
}

// Test functions (user-safe only)
function testHealthCheck() {
  group('health', () => {
    const res = http.get(`${BASE_URL}/health`);
    const success = check(res, {
      'health check 200': (r) => r.status === 200,
    });
    if (!success) errorRate.add(1);
    apiOperations.add(1);
  });
}

function testAuth() {
  group('auth', () => {
    const token = ensureAuth();
    const success = check({ token }, {
      'auth successful': (data) => data.token !== null,
    });
    if (!success) errorRate.add(1);
  });
}

function testUserProfile() {
  group('users', () => {
    // Get current user info (correct endpoint - user safe)
    const res = http.get(`${BASE_URL}/api/v1/auths/`, jsonHeaders());
    const success = check(res, {
      'current user info 200': (r) => r.status === 200,
    });
    if (!success) errorRate.add(1);
    apiOperations.add(1);
  });
}

function testChats() {
  group('chats', () => {
    // User's own chats only
    const res = http.get(`${BASE_URL}/api/v1/chats/`, jsonHeaders());
    const success = check(res, {
      'chats list 200': (r) => r.status === 200,
    });
    if (!success) errorRate.add(1);
    chatOperations.add(1);
  });
}

function testModels() {
  group('models', () => {
    // Primary models endpoint (used by frontend)
    const res = http.get(`${BASE_URL}/api/models`, jsonHeaders());
    const success = check(res, {
      'models list 200': (r) => r.status === 200,
    });
    if (!success) errorRate.add(1);
    apiOperations.add(1);
  });
}

function testPrompts() {
  group('prompts', () => {
    // User accessible prompts
    const res = http.get(`${BASE_URL}/api/v1/prompts/`, jsonHeaders());
    const success = check(res, {
      'prompts list 200 or 404': (r) => r.status === 200 || r.status === 404,
    });
    if (!success) errorRate.add(1);
    apiOperations.add(1);
  });
}

function testDocuments() {
  group('documents', () => {
    // User's own documents
    const res = http.get(`${BASE_URL}/api/v1/documents/`, jsonHeaders());
    const success = check(res, {
      'documents list 200 or 404': (r) => r.status === 200 || r.status === 404,
    });
    if (!success) errorRate.add(1);
    apiOperations.add(1);
  });
}

function testKnowledge() {
  group('knowledge', () => {
    // User's knowledge base
    const res = http.get(`${BASE_URL}/api/v1/knowledge/`, jsonHeaders());
    const success = check(res, {
      'knowledge list 200 or 404': (r) => r.status === 200 || r.status === 404,
    });
    if (!success) errorRate.add(1);
    apiOperations.add(1);
  });
}

function testTools() {
  group('tools', () => {
    // Available tools (user accessible)
    const res = http.get(`${BASE_URL}/api/v1/tools/`, jsonHeaders());
    const success = check(res, {
      'tools list 200 or 404': (r) => r.status === 200 || r.status === 404,
    });
    if (!success) errorRate.add(1);
    apiOperations.add(1);
  });
}

function testFileUpload() {
  if (!TEST_FILE_UPLOAD) return;

  group('files', () => {
    // Create a comprehensive PDF for testing with actual content
    const pdfHeader = '%PDF-1.4\n';

    // Catalog object
    const pdfCatalog = '1 0 obj\n<<\n/Type /Catalog\n/Pages 2 0 R\n>>\nendobj\n';

    // Pages object
    const pdfPages = '2 0 obj\n<<\n/Type /Pages\n/Kids [3 0 R]\n/Count 1\n>>\nendobj\n';

    // Page object with content reference
    const pdfPage = '3 0 obj\n<<\n/Type /Page\n/Parent 2 0 R\n/MediaBox [0 0 612 792]\n/Contents 4 0 R\n/Resources <<\n/Font <<\n/F1 5 0 R\n>>\n>>\n>>\nendobj\n';

    // Content stream with actual text
    const pdfContent = '4 0 obj\n<<\n/Length 200\n>>\nstream\nBT\n/F1 12 Tf\n50 750 Td\n(K6 Performance Test Document) Tj\n0 -20 Td\n(Generated for Open WebUI Testing) Tj\n0 -20 Td\n(Test Content: File Upload Functionality) Tj\n0 -20 Td\n(Date: ' + new Date().toISOString().split('T')[0] + ') Tj\nET\nendstream\nendobj\n';

    // Font object
    const pdfFont = '5 0 obj\n<<\n/Type /Font\n/Subtype /Type1\n/BaseFont /Helvetica\n>>\nendobj\n';

    // Cross-reference table
    const pdfXref = 'xref\n0 6\n0000000000 65535 f \n0000000010 00000 n \n0000000079 00000 n \n0000000173 00000 n \n0000000370 00000 n \n0000000624 00000 n \n';

    // Trailer
    const pdfTrailer = 'trailer\n<<\n/Size 6\n/Root 1 0 R\n>>\nstartxref\n724\n%%EOF';

    const pdfFileContent = pdfHeader + pdfCatalog + pdfPages + pdfPage + pdfContent + pdfFont + pdfXref + pdfTrailer;

    const formData = {
      file: http.file(pdfFileContent, 'k6-test-document.pdf', 'application/pdf'),
      process: 'true',
    };

    const res = http.post(`${BASE_URL}/api/v1/files/`, formData, formHeaders());
    const success = check(res, {
      'file upload 200': (r) => r.status === 200,
    });
    if (!success) errorRate.add(1);
    fileOperations.add(1);
  });
}

// Main test function
export default function () {
  // Ensure authentication
  const token = ensureAuth();
  if (!token) {
    console.log('Skipping tests due to auth failure');
    errorRate.add(1);
    return;
  }

  // Test selection based on scenario (varied load)
  const scenario = Math.random();
  
  if (scenario < 0.1) {
    // 10% - Health check only (lightest)
    testHealthCheck();
  } else if (scenario < 0.3) {
    // 20% - Basic user tests
    testAuth();
    testUserProfile();
    sleep(0.5);
  } else if (scenario < 0.6) {
    // 30% - Core user functionality
    testChats();
    testModels();
    sleep(0.5);
  } else if (scenario < 0.85) {
    // 25% - Extended user tests
    testPrompts();
    testDocuments();
    testKnowledge();
    testTools();
    sleep(1);
  } else {
    // 15% - Full user test suite including file upload
    testAuth();
    testUserProfile();
    testChats();
    testModels();
    testPrompts();
    testDocuments();
    testKnowledge();
    testTools();
    testFileUpload();
    sleep(1.5);
  }
}

export function teardown(data) {
  console.log('=== User Load Test Results ===');
  console.log(`Authentication operations: ${authOperations.count}`);
  console.log(`Chat operations: ${chatOperations.count}`);
  console.log(`File operations: ${fileOperations.count}`);
  console.log(`Total API operations: ${apiOperations.count}`);
  console.log(`Test type: ${testType}`);
  console.log(`Target users: ${vus}`);
  console.log(`Duration: ${duration}`);
  if (rps > 0) {
    console.log(`Target RPS: ${rps}`);
  }
  console.log('Note: Only user-accessible endpoints were tested (no admin APIs)');
}