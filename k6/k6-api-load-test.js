/*
  Open WebUI API Load Test Script - Unified Version
  
  Comprehensive API testing for all Open WebUI endpoints (excluding AI chat)
  Combines enhanced load testing with legacy compatibility
  
  Environment variables:
  - BASE_URL: target URL (default: http://localhost:8088)
  - EMAIL: existing user email (REQUIRED)
  - PASSWORD: existing user password (REQUIRED)
  - VUS: virtual users (default: 10)
  - DURATION: test duration (default: 10m)
  - RPS: requests per second (overrides VUS/duration if set)
  - TEST_TYPE: load test type (load, spike, stress, volume, simple)
  - TEST_FILE_UPLOAD: enable file upload tests (default: false)
  - TEST_DOCUMENTS: enable document/knowledge tests (default: true)

  Tested endpoints (verified with actual Open WebUI API):
  - Authentication (signin) - POST /api/v1/auths/signin
  - Current user info - GET /api/v1/auths/
  - User list (admin) - GET /api/v1/users/ (may return 401/403)
  - Chat listing - GET /api/v1/chats/
  - Models - GET /api/models (primary) & /api/v1/models/
  - Document/Knowledge - GET /api/v1/documents/, /api/v1/knowledge/
  - Prompts - GET /api/v1/prompts/
  - Tools - GET /api/v1/tools/
  - File upload - POST /api/v1/files/ (optional)
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
const TEST_DOCUMENTS = (__ENV.TEST_DOCUMENTS || 'true').toLowerCase() === 'true';

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
      // Simple constant load (legacy compatibility)
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
          { duration: '1m', target: vus * 3 },               // Sudden spike
          { duration: '3m', target: vus * 3 },               // Maintain spike  
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
      // Stress test - find breaking point
      opt = {
        stages: [
          { duration: '2m', target: 50 },    // Warm up
          { duration: '3m', target: 100 },   // Moderate load
          { duration: '3m', target: 300 },   // High load
          { duration: '3m', target: 500 },   // Very high load
          { duration: '3m', target: 1000 },  // Extreme load
          { duration: '10m', target: 1000 }, // Sustain extreme load
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
          { duration: '5m', target: Math.ceil(vus * 1.5) }, // Ramp up
          { duration: '30m', target: Math.ceil(vus * 1.5) }, // Long sustained load
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

// Test functions
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
    // Get current user info (correct endpoint)
    const profileRes = http.get(`${BASE_URL}/api/v1/auths/`, jsonHeaders());
    const profileSuccess = check(profileRes, {
      'current user info 200': (r) => r.status === 200,
    });

    // Only test admin endpoints if TEST_TYPE includes admin functionality
    if (testType === 'load' || testType === 'stress' || testType === 'volume') {
      // Try users list (admin only - expect 401/403 for non-admin users)
      const listRes = http.get(`${BASE_URL}/api/v1/users/`, jsonHeaders());
      check(listRes, {
        'users list 200 or 403': (r) => r.status === 200 || r.status === 403 || r.status === 401,
      });
    }

    // Success if profile works (list may fail for non-admin users)
    if (!profileSuccess) {
      errorRate.add(1);
    }
    apiOperations.add(1);
  });
}

function testChats() {
  group('chats', () => {
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
    const mainRes = http.get(`${BASE_URL}/api/models`, jsonHeaders());
    const mainSuccess = check(mainRes, {
      'main models endpoint 200': (r) => r.status === 200,
    });
    
    // Secondary models endpoint
    const altRes = http.get(`${BASE_URL}/api/v1/models/`, jsonHeaders());
    const altSuccess = check(altRes, {
      'alt models endpoint 200 or 404': (r) => r.status === 200 || r.status === 404,
    });
    
    // Success if either endpoint works
    if (!mainSuccess && !altSuccess) {
      errorRate.add(1);
    }
    apiOperations.add(1);
  });
}

function testPrompts() {
  group('prompts', () => {
    const res = http.get(`${BASE_URL}/api/v1/prompts/`, jsonHeaders());
    const success = check(res, {
      'prompts list 200 or 404': (r) => r.status === 200 || r.status === 404,
    });
    if (!success) errorRate.add(1);
    apiOperations.add(1);
  });
}

function testDocuments() {
  if (!TEST_DOCUMENTS) return;
  
  group('documents', () => {
    const res = http.get(`${BASE_URL}/api/v1/documents/`, jsonHeaders());
    const success = check(res, {
      'documents list 200 or 404': (r) => r.status === 200 || r.status === 404,
    });
    if (!success) errorRate.add(1);
    apiOperations.add(1);
  });
}

function testKnowledge() {
  if (!TEST_DOCUMENTS) return;

  group('knowledge', () => {
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
    // Create a simple PDF-like content for testing
    const pdfHeader = '%PDF-1.4\n';
    const pdfContent = '1 0 obj\n<<\n/Type /Catalog\n/Pages 2 0 R\n>>\nendobj\n';
    const pdfPages = '2 0 obj\n<<\n/Type /Pages\n/Kids [3 0 R]\n/Count 1\n>>\nendobj\n';
    const pdfPage = '3 0 obj\n<<\n/Type /Page\n/Parent 2 0 R\n/MediaBox [0 0 612 792]\n>>\nendobj\n';
    const pdfXref = 'xref\n0 4\n0000000000 65535 f\n0000000010 00000 n\n0000000079 00000 n\n0000000173 00000 n\n';
    const pdfTrailer = 'trailer\n<<\n/Size 4\n/Root 1 0 R\n>>\nstartxref\n242\n%%EOF';
    const pdfFileContent = pdfHeader + pdfContent + pdfPages + pdfPage + pdfXref + pdfTrailer;

    const formData = {
      file: http.file(pdfFileContent, 'k6-test-document.pdf', 'application/pdf'),
      process: 'false',
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

  // Test selection based on scenario (to vary load)
  const scenario = Math.random();
  
  if (scenario < 0.1) {
    // 10% - Health check only (lightest)
    testHealthCheck();
  } else if (scenario < 0.3) {
    // 20% - Basic API tests
    testAuth();
    testUserProfile();
    sleep(0.5);
  } else if (scenario < 0.6) {
    // 30% - Core functionality
    testChats();
    testModels();
    sleep(0.5);
  } else if (scenario < 0.85) {
    // 25% - Extended API tests
    testPrompts();
    testDocuments();
    testKnowledge();
    testTools();
    sleep(1);
  } else {
    // 15% - Full test suite including file upload
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
  console.log('=== API Load Test Results ===');
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
}