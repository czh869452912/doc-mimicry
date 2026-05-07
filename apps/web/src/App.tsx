import { Route, Routes } from "react-router-dom";
import { AppShell } from "./shell/AppShell";

export function App() {
  return (
    <Routes>
      <Route path="*" element={<AppShell />} />
    </Routes>
  );
}
