// Turns a fetch Response into its JSON body, or throws an Error carrying FastAPI's `detail`
// (e.g. "Context 'x' already exists (#12)") so a caller can show the server's reason as-is.
export async function checked<T>(response: Response, path: string): Promise<T> {
  if (!response.ok) {
    const text = await response.text();
    let detail = text;
    try {
      detail = JSON.parse(text).detail ?? text;
    } catch {
      // non-JSON error body: show it as-is
    }
    throw new Error(`${path} -> ${response.status}: ${typeof detail === 'string' ? detail : JSON.stringify(detail)}`);
  }
  return response.json();
}

export async function sendJson<T>(method: 'POST' | 'PUT' | 'PATCH', path: string, body: unknown): Promise<T> {
  const response = await fetch(`/api${path}`, {
    method,
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  return checked(response, path);
}
