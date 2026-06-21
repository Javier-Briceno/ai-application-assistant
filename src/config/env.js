export const WEBHOOK_URL = 'https://n8n.javierbriceno.com/webhook/job-application';

export const API_ENDPOINTS = Object.freeze({
  analyzePosting: WEBHOOK_URL,
  listProfiles: 'https://n8n.javierbriceno.com/webhook/profiles',
  profileSetup: 'https://n8n.javierbriceno.com/webhook/profile-setup',
});

export const REQUEST_TIMEOUT_MS = 300000; // 5 minutes — workflow takes ~3 min

export const APP_FLAGS = Object.freeze({
  enableDebugLogs: false,
  enableMockResponse: false,
});