const BASE = import.meta.env.VITE_API_BASE ?? "/api";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const token = localStorage.getItem("token");
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(init?.headers ?? {}),
    },
  });
  if (!res.ok) throw new Error(`API ${res.status}: ${await res.text()}`);
  return res.json();
}

export const placeOrder = (body: unknown) =>
  request("/orders/", { method: "POST", body: JSON.stringify(body) });

export const login = (credentials: { username: string; password: string }) =>
  request<{ access_token: string }>("/auth/token", {
    method: "POST",
    body: JSON.stringify(credentials),
  });
