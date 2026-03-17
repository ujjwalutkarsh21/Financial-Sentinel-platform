// === Base API client ===

const BASE_URL = import.meta.env.VITE_API_URL || '';

interface RequestOptions {
  method?: string;
  body?: unknown;
  headers?: Record<string, string>;
}

async function request<T>(url: string, options: RequestOptions = {}): Promise<T> {
  const { method = 'GET', body, headers = {} } = options;

  const config: RequestInit = {
    method,
    headers: {
      ...headers,
    },
  };

  if (body && !(body instanceof FormData)) {
    config.headers = { ...config.headers, 'Content-Type': 'application/json' } as Record<string, string>;
    config.body = JSON.stringify(body);
  } else if (body instanceof FormData) {
    config.body = body;
  }

  const response = await fetch(`${BASE_URL}${url}`, config);

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(`API Error ${response.status}: ${errorText}`);
  }

  return response.json();
}

export function get<T>(url: string): Promise<T> {
  return request<T>(url);
}

export function post<T>(url: string, body: unknown): Promise<T> {
  return request<T>(url, { method: 'POST', body });
}

export function upload<T>(url: string, file: File): Promise<T> {
  const formData = new FormData();
  formData.append('file', file);
  return request<T>(url, { method: 'POST', body: formData });
}
