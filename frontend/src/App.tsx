import { Routes, Route, Navigate } from "react-router";
import Landing from "./pages/Landing";
import Dashboard from "./pages/Dashboard";
import Applications from "./pages/Applications";
import Tailor from "./pages/Tailor";
import AppLayout from "./components/AppLayout";
import RequireAuth from "./auth/RequireAuth";
import Settings from "./pages/Settings";

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Landing />} />
      <Route element={<RequireAuth />}>
        <Route element={<AppLayout />}>
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/applications" element={<Applications />} />
          <Route path="/settings" element={<Settings />} />
        </Route>
      <Route path="/tailor" element={<Tailor />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
