import { API_ENDPOINTS, REQUEST_TIMEOUT_MS } from '../../../config/env.js';

export async function fetchProfiles() {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 30_000);

  try {
    const response = await fetch(API_ENDPOINTS.listProfiles, {
      method: 'GET',
      headers: { 'Accept': 'application/json' },
      signal: controller.signal,
    });

    if (!response.ok) {
      throw createApiError(
        'FETCH_PROFILES_ERROR',
        `Failed with status ${response.status}.`
      );
    }

    const data = await response.json();

    if (!Array.isArray(data)) {
      throw createApiError('FETCH_PROFILES_ERROR', 'Expected an array of profiles.');
    }

    return data;
  } catch (error) {
    if (error?.name === 'AbortError') {
      throw createApiError('FETCH_PROFILES_ERROR', 'Request timed out.');
    }
    if (error?.code) throw error;
    throw createApiError(
      'FETCH_PROFILES_ERROR',
      error?.message || 'Could not load profiles.'
    );
  } finally {
    clearTimeout(timeoutId);
  }
}

export async function saveProfile(profileData) {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);

  try {
    const response = await fetch(API_ENDPOINTS.profileSetup, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
      },
      body: JSON.stringify(profileData),
      signal: controller.signal,
    });

    if (!response.ok) {
      throw createApiError(
        'SAVE_PROFILE_ERROR',
        `Failed with status ${response.status}.`
      );
    }

    const data = await response.json();

    if (!data?.success) {
      throw createApiError('SAVE_PROFILE_ERROR', 'Profile save failed.');
    }

    return data;
  } catch (error) {
    if (error?.name === 'AbortError') {
      throw createApiError('SAVE_PROFILE_ERROR', 'Request timed out.');
    }
    if (error?.code) throw error;
    throw createApiError(
      'SAVE_PROFILE_ERROR',
      error?.message || 'Could not save profile.'
    );
  } finally {
    clearTimeout(timeoutId);
  }
}

function createApiError(code, message) {
  const error = new Error(message);
  error.name = 'ProfilesApiError';
  error.code = code;
  return error;
}
