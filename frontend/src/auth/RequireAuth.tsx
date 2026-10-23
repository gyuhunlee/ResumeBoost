import { Navigate, Outlet } from "react-router";
import { useAuth } from "./AuthProvider";

export default function RequireAuth() {
  const { session, loading } = useAuth();
  if (loading) return <div className="p-8 text-slate-500">Loading…</div>;
  if (!session) return <Navigate to="/" replace />;
  return <Outlet />;
}