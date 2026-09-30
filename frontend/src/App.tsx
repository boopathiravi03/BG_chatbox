import React from "react";
import { AuthProvider, useAuth } from "./context/AuthContext";
import AuthPage from "./pages/AuthPage";
import Home from "./pages/Home";
import CustomCursor from "./components/ui/CustomCursor";
import BrandIntro from "./components/ui/BrandIntro";
import { ToastProvider } from "./context/ToastContext";

function MainApp() {
  const { isAuthenticated, isLoading } = useAuth();

  if (isLoading) {
    return (
      <div className="flex h-screen w-screen items-center justify-center bg-[#09090b] text-white">
        <div className="flex items-center gap-3">
          <div className="h-6 w-6 animate-spin rounded-full border-2 border-indigo-500 border-t-transparent" />
          <span className="text-sm font-medium text-zinc-400">Loading BG AI...</span>
        </div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return <AuthPage />;
  }

  return <Home />;
}

export default function App() {
  return (
    <ToastProvider>
      <AuthProvider>
        <BrandIntro />
        <CustomCursor />
        <MainApp />
      </AuthProvider>
    </ToastProvider>
  );
}
