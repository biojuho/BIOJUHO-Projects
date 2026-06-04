/* global afterEach, describe, expect, it, vi */

const FIREBASE_ENV_KEYS = [
  'VITE_FIREBASE_API_KEY',
  'VITE_FIREBASE_AUTH_DOMAIN',
  'VITE_FIREBASE_PROJECT_ID',
  'VITE_FIREBASE_STORAGE_BUCKET',
  'VITE_FIREBASE_MESSAGING_SENDER_ID',
  'VITE_FIREBASE_APP_ID',
];

afterEach(() => {
  vi.unstubAllEnvs();
  vi.resetModules();
});

describe('firebase config boundary', () => {
  it('uses inert auth when Firebase env is missing', async () => {
    for (const key of FIREBASE_ENV_KEYS) {
      vi.stubEnv(key, '');
    }

    const firebase = await import('./firebase');

    expect(firebase.isFirebaseConfigured).toBe(false);
    expect(firebase.default).toBeNull();
    expect(firebase.auth.currentUser).toBeNull();
    expect(firebase.googleProvider).toBeNull();
  });

  it('rejects template placeholder values as usable Firebase config', async () => {
    vi.stubEnv('VITE_FIREBASE_API_KEY', 'your_api_key');
    vi.stubEnv('VITE_FIREBASE_AUTH_DOMAIN', 'your_project.firebaseapp.com');
    vi.stubEnv('VITE_FIREBASE_PROJECT_ID', 'your_project_id');
    vi.stubEnv('VITE_FIREBASE_STORAGE_BUCKET', 'your_project.appspot.com');
    vi.stubEnv('VITE_FIREBASE_MESSAGING_SENDER_ID', 'your_sender_id');
    vi.stubEnv('VITE_FIREBASE_APP_ID', 'your_app_id');

    const firebase = await import('./firebase');

    expect(firebase.isFirebaseConfigured).toBe(false);
    expect(firebase.auth.currentUser).toBeNull();
  });
});
