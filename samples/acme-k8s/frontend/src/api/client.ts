const BASE = import.meta.env.VITE_API_BASE ?? "/api/v1";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const token = localStorage.getItem("jwt");
  const res = await fetch(`${BASE}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(options?.headers ?? {}),
    },
  });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json();
}

export const placeOrder = (body: unknown) =>
  request("/orders", { method: "POST", body: JSON.stringify(body) });

export const getProducts = () => request<unknown[]>("/products");
