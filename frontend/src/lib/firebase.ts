import { initializeApp, getApps, getApp } from "firebase/app";
import { getAuth, GoogleAuthProvider } from "firebase/auth";

export const firebaseConfig = {
  apiKey: import.meta.env.VITE_FIREBASE_API_KEY || "AIzaSyAc7V0mjD2DkOEUCixVOlcmI2uip-_eAI4",
  authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN || "bg-platform-4b882.firebaseapp.com",
  projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID || "bg-platform-4b882",
  storageBucket: import.meta.env.VITE_FIREBASE_STORAGE_BUCKET || "bg-platform-4b882.firebasestorage.app",
  messagingSenderId: import.meta.env.VITE_FIREBASE_MESSAGING_SENDER_ID || "1045610580763",
  appId: import.meta.env.VITE_FIREBASE_APP_ID || "1:1045610580763:web:c6b5955dd9e8fca702e1be",
  measurementId: import.meta.env.VITE_FIREBASE_MEASUREMENT_ID || "G-CMBRKJZ9RZ",
};

// Initialize or reuse Firebase App singleton
const app = getApps().length > 0 ? getApp() : initializeApp(firebaseConfig);

export const auth = getAuth(app);
export const googleProvider = new GoogleAuthProvider();
export default app;

