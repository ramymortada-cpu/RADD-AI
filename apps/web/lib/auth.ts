"use client";

export function saveTokens(accessToken: string, refreshToken: string) {
  localStorage.setItem("radd_access_token", accessToken);
  localStorage.setItem("radd_refresh_token", refreshToken);
}

export function clearTokens() {
  localStorage.removeItem("radd_access_token");
  localStorage.removeItem("radd_refresh_token");
}

export function isAuthenticated(): boolean {
  if (typeof window === "undefined") return false;
  return !!localStorage.getItem("radd_access_token");
}
