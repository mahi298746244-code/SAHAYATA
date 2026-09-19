import { lazy, Suspense } from "react";
import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import { useAuth } from "./context/AuthContext";
import CitizenLayout from "./components/CitizenLayout";
import ConsoleLayout from "./components/ConsoleLayout";
import Login from "./pages/Login";
import Register from "./pages/Register";
import Dashboard from "./pages/citizen/Dashboard";

const NewReport = lazy(() => import("./pages/citizen/NewReport"));
const MyReports = lazy(() => import("./pages/citizen/MyReports"));
const ProblemDetail = lazy(() => import("./pages/ProblemDetail"));
const MapPage = lazy(() => import("./pages/MapPage"));
const PriorityQueue = lazy(() => import("./pages/console/PriorityQueue"));
const Problems = lazy(() => import("./pages/console/Problems"));
const ActionsBoard = lazy(() => import("./pages/console/ActionsBoard"));
const Analytics = lazy(() => import("./pages/console/Analytics"));
const AdminUsers = lazy(() => import("./pages/admin/AdminUsers"));
const Simulator = lazy(() => import("./pages/admin/Simulator"));

function Splash() {
  return (
    <div className="flex h-full items-center justify-center">
      <div className="h-10 w-10 animate-spin rounded-full border-4 border-indigo-200 border-t-indigo-600" />
    </div>
  );
}

function Page({ children }: { children: React.ReactNode }) {
  return <Suspense fallback={<Splash />}>{children}</Suspense>;
}

function Protected({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  const loc = useLocation();
  if (loading) return <Splash />;
  if (!user) return <Navigate to="/login" state={{ from: loc.pathname }} replace />;
  return <>{children}</>;
}

function RoleGate({ roles, children }: { roles: string[]; children: React.ReactNode }) {
  const { user } = useAuth();
  if (!user || !roles.includes(user.role)) return <Navigate to="/" replace />;
  return <>{children}</>;
}

export default function App() {
  const { user, loading } = useAuth();

  if (loading) return <Splash />;

  const home = !user ? "/welcome" : user.role === "citizen" ? "/app" : "/console";

  return (
    <Routes>
      <Route path="/login" element={user ? <Navigate to={home} replace /> : <Login />} />
      <Route path="/register" element={user ? <Navigate to={home} replace /> : <Register />} />

      <Route
        path="/welcome"
        element={!user ? <Login /> : <Navigate to={home} replace />}
      />

      <Route
        path="/app"
        element={
          <Protected>
            <RoleGate roles={["citizen", "admin"]}>
              <CitizenLayout />
            </RoleGate>
          </Protected>
        }
      >
        <Route index element={<Dashboard />} />
        <Route path="report" element={<Page><NewReport /></Page>} />
        <Route path="reports" element={<Page><MyReports /></Page>} />
        <Route path="map" element={<Page><MapPage /></Page>} />
        <Route path="problems/:code" element={<Page><ProblemDetail /></Page>} />
      </Route>

      <Route
        path="/console"
        element={
          <Protected>
            <RoleGate roles={["authority", "admin"]}>
              <ConsoleLayout />
            </RoleGate>
          </Protected>
        }
      >
        <Route index element={<Page><PriorityQueue /></Page>} />
        <Route path="problems" element={<Page><Problems /></Page>} />
        <Route path="actions" element={<Page><ActionsBoard /></Page>} />
        <Route path="map" element={<Page><MapPage staff /></Page>} />
        <Route path="analytics" element={<Page><Analytics /></Page>} />
        <Route path="simulator" element={<Page><Simulator /></Page>} />
        <Route path="problems/:code" element={<Page><ProblemDetail staff /></Page>} />
      </Route>

      <Route
        path="/admin/users"
        element={
          <Protected>
            <RoleGate roles={["admin"]}>
              <ConsoleLayout />
            </RoleGate>
          </Protected>
        }
      >
        <Route index element={<Page><AdminUsers /></Page>} />
      </Route>

      <Route path="*" element={<Navigate to={home} replace />} />
    </Routes>
  );
}
