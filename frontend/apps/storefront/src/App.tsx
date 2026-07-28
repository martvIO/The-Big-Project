import { ToastProvider } from "@boutique/ui";
import { StorefrontLayout } from "./components/StorefrontLayout";
import { Router } from "./router";

export function App() {
  return (
    <ToastProvider>
      <StorefrontLayout>
        <Router />
      </StorefrontLayout>
    </ToastProvider>
  );
}
