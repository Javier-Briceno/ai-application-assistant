import { fetchProfiles, saveProfile } from '../api/profilesApi.js';
import { UI_TEXT } from '../../../shared/constants/uiText.js';

const STORAGE_KEY = 'job_app_active_profile_id';

export function createProfileController({ app, profileSelector, profileModal }) {
  async function loadProfiles() {
    profileSelector.setLoading(true);

    try {
      const profiles = await fetchProfiles();

      app.state.profiles = profiles;
      app.state.profilesLoaded = true;
      app.state.profilesError = null;

      // Restore persisted selection, verify it still exists
      const persistedId = loadPersistedProfileId();
      const matched = profiles.find((p) => p.id === persistedId);
      const activeId = matched ? persistedId : null;

      app.state.activeProfileId = activeId;
      profileSelector.updateProfiles(profiles, activeId);
    } catch (error) {
      app.state.profilesLoaded = true;
      app.state.profilesError = error.message;
      profileSelector.setLoading(false);
      profileSelector.setError(UI_TEXT.profiles.loadError);
    }
  }

  function onProfileChange(profileId) {
    app.state.activeProfileId = profileId;
    persistProfileId(profileId);
  }

  function onCreateClick() {
    profileModal.open(null);
  }

  function onEditClick(profileId) {
    const profile = app.state.profiles.find((p) => p.id === profileId);
    if (profile) profileModal.open(profile);
  }

  async function onSave(profileData) {
    // Throws if save fails — modal shows the error
    const result = await saveProfile(profileData);

    // Reload list — don't fail the save if this fails
    try {
      const profiles = await fetchProfiles();
      app.state.profiles = profiles;

      const savedId = result.profile_id;
      app.state.activeProfileId = savedId;
      persistProfileId(savedId);

      profileSelector.updateProfiles(profiles, savedId);
    } catch {
      profileSelector.setError('Profile saved. Could not refresh list — please reload.');
    }

    return result;
  }

  // Kick off initial load
  loadProfiles();

  return { onProfileChange, onCreateClick, onEditClick, onSave };
}

export function loadPersistedProfileId() {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    return stored ? Number(stored) : null;
  } catch {
    return null;
  }
}

export function persistProfileId(profileId) {
  try {
    if (profileId) {
      localStorage.setItem(STORAGE_KEY, String(profileId));
    } else {
      localStorage.removeItem(STORAGE_KEY);
    }
  } catch {
    // localStorage unavailable — silenciar
  }
}
