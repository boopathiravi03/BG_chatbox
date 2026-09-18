import Home from "./pages/Home";
import CustomCursor from "./components/ui/CustomCursor";
import BrandIntro from "./components/ui/BrandIntro";
import { ToastProvider } from "./context/ToastContext";

export default function App() {
  return (
    <ToastProvider>
      <BrandIntro />
      <CustomCursor />
      <Home />
    </ToastProvider>
  );
}
