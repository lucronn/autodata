// Packaging only. The customer UI owns app initialization and persistence.
export { initializeApp } from 'firebase/app';
export {
  initializeAuth,
  inMemoryPersistence,
  setPersistence,
  GoogleAuthProvider,
  browserPopupRedirectResolver,
  signInWithPopup,
  reauthenticateWithPopup,
  getIdTokenResult,
  signOut,
} from 'firebase/auth';
