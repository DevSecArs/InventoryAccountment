import { apiRequest } from "./client";

export interface User {
  id: string;
  login: string;
  full_name: string;
  email: string | null;
  role: "admin" | "operator" | "reporter";
}

export interface AuthResult {
  user: User;
  csrf_token: string;
}

export interface Credentials {
  login: string;
  password: string;
}

export interface Registration extends Credentials {
  full_name: string;
  email?: string;
}

export function getCurrentUser() {
  return apiRequest<AuthResult>("/api/v1/auth/me");
}

export function login(credentials: Credentials) {
  return apiRequest<AuthResult>("/api/v1/auth/login", { method: "POST", body: JSON.stringify(credentials) });
}

export function register(payload: Registration) {
  return apiRequest<AuthResult>("/api/v1/auth/register", { method: "POST", body: JSON.stringify(payload) });
}

export function logout() {
  return apiRequest<void>("/api/v1/auth/logout", { method: "POST" });
}

export function updateProfile(payload: Pick<User, "full_name" | "email">) {
  return apiRequest<User>("/api/v1/auth/me", { method: "PUT", body: JSON.stringify(payload) });
}
