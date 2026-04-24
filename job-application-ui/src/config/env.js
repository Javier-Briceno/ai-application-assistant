export const WEBHOOK_URL = 'http://localhost:5678/webhook/job-application';

export const API_ENDPOINTS = Object.freeze({
  analyzePosting: WEBHOOK_URL,
  listProfiles: 'http://localhost:5678/webhook/profiles',
  profileSetup: 'http://localhost:5678/webhook/profile-setup',
});

export const REQUEST_TIMEOUT_MS = 300000; // 5 minutes — workflow takes ~3 min

export const APP_FLAGS = Object.freeze({
  enableDebugLogs: false,
  enableMockResponse: false,
});