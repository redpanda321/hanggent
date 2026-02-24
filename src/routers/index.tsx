// ========= Copyright 2025-2026 @ Hanggent.AI All Rights Reserved. =========
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//     http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.
// ========= Copyright 2025-2026 @ Hanggent.AI All Rights Reserved. =========

import { useAuthStore } from '@/store/authStore';
import { features, isCommunityEdition } from '@/lib/edition';
import { lazy, useEffect, useReducer } from 'react';
import { Navigate, Outlet, Route, Routes } from 'react-router-dom';

import Layout from '@/components/Layout';
// Lazy load page components
const Login = lazy(() => import('@/pages/Login'));
const Signup = lazy(() => import('@/pages/SignUp'));
const Home = lazy(() => import('@/pages/Home'));
const History = lazy(() => import('@/pages/History'));
const Gateway = lazy(() => import('@/pages/Gateway'));
const NotFound = lazy(() => import('@/pages/NotFound'));
const Pricing = lazy(() => import('@/pages/Pricing'));

interface AuthState {
  loading: boolean;
  isAuthenticated: boolean;
  initialized: boolean;
}

type AuthAction =
  | { type: 'INITIALIZE'; payload: { isAuthenticated: boolean } }
  | { type: 'LOGOUT' };

const authReducer = (state: AuthState, action: AuthAction): AuthState => {
  switch (action.type) {
    case 'INITIALIZE':
      return {
        loading: false,
        isAuthenticated: action.payload.isAuthenticated,
        initialized: true,
      };
    case 'LOGOUT':
      return {
        loading: false,
        isAuthenticated: false,
        initialized: true,
      };
    default:
      return state;
  }
};

// Route guard: Check if user is logged in
const ProtectedRoute = () => {
  const [state, dispatch] = useReducer(authReducer, {
    loading: false,
    isAuthenticated: false,
    initialized: false,
  });

  const { token, logout } = useAuthStore();
  useEffect(() => {
    // Community edition: always authenticated (NoopAuthProvider seeds token)
    if (isCommunityEdition) {
      dispatch({ type: 'INITIALIZE', payload: { isAuthenticated: true } });
      return;
    }
    dispatch({ type: 'INITIALIZE', payload: { isAuthenticated: !!token } });
  }, [token, logout]);

  if (state.loading || !state.initialized) {
    return (
      <div className="flex h-screen items-center justify-center">
        <div className="h-8 w-8 animate-spin rounded-full border-b-2 border-blue-600"></div>
      </div>
    );
  }
  return state.isAuthenticated ? <Outlet /> : <Navigate to="/login" replace />;
};

// Main route configuration
const AppRoutes = () => (
  <Routes>
    {/* Cloud-only routes: login, signup, pricing, gateway */}
    {features.auth && <Route path="/login" element={<Login />} />}
    {features.auth && <Route path="/signup" element={<Signup />} />}
    {features.billing && <Route path="/pricing" element={<Pricing />} />}
    <Route element={<ProtectedRoute />}>
      <Route element={<Layout />}>
        <Route path="/" element={<Home />} />
        <Route path="/history" element={<History />} />
        {features.gateway && (
          <Route path="/gateway" element={<Gateway />} />
        )}
        <Route
          path="/setting"
          element={<Navigate to="/history?tab=settings" replace />}
        />
        <Route
          path="/setting/*"
          element={<Navigate to="/history?tab=settings" replace />}
        />
      </Route>
    </Route>
    <Route path="*" element={<NotFound />} />
  </Routes>
);

export default AppRoutes;
