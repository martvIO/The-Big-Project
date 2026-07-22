import { tokens } from "@boutique/ui";

export function App() {
  return (
    <main
      className="flex min-h-screen items-center justify-center"
      style={{ backgroundColor: tokens.color.cream, color: tokens.color.ink }}
    >
      <div className="text-center">
        <h1 className="text-3xl font-light tracking-wide">ניהול הבוטיק</h1>
        <p className="mt-2 text-sm" style={{ color: tokens.color.gold }}>
          Manage placeholder — owner settings arrive with Feature 7
        </p>
      </div>
    </main>
  );
}
