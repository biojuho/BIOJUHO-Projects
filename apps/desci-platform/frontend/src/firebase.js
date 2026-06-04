/**
 * Firebase Configuration
 * All config values loaded from environment variables
 */
import { initializeApp } from 'firebase/app';
import { getAuth, GoogleAuthProvider } from 'firebase/auth';

const firebaseConfig = {
    apiKey: import.meta.env.VITE_FIREBASE_API_KEY,
    authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN,
    projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID,
    storageBucket: import.meta.env.VITE_FIREBASE_STORAGE_BUCKET,
    messagingSenderId: import.meta.env.VITE_FIREBASE_MESSAGING_SENDER_ID,
    appId: import.meta.env.VITE_FIREBASE_APP_ID,
};

const REQUIRED_CONFIG_KEYS = [
    'apiKey',
    'authDomain',
    'projectId',
    'storageBucket',
    'messagingSenderId',
    'appId',
];

function hasUsableConfigValue(value) {
    return typeof value === 'string' && value.trim() !== '' && !value.startsWith('your_');
}

export const isFirebaseConfigured = REQUIRED_CONFIG_KEYS.every((key) => hasUsableConfigValue(firebaseConfig[key]));

// Initialize Firebase only when the deployed environment supplies a complete config.
// Local smoke and public route checks must not blank the app because auth credentials are absent.
const app = isFirebaseConfigured ? initializeApp(firebaseConfig) : null;

// Auth exports
export const auth = isFirebaseConfigured ? getAuth(app) : { currentUser: null };
export const googleProvider = isFirebaseConfigured ? new GoogleAuthProvider() : null;

export default app;
