// Typed fetch wrapper. All requests go to same-origin /api (proxied to FastAPI by next.config.ts).

export class ApiError extends Error {
  constructor(public status: number, message: string, public body?: unknown) {
    super(message);
  }
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`/api${path}`, {
      method,
      credentials: "include",
      headers: body !== undefined ? { "Content-Type": "application/json" } : undefined,
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
  } catch {
    throw new ApiError(0, "เชื่อมต่อเซิร์ฟเวอร์ไม่ได้ กรุณาตรวจสอบการเชื่อมต่อแล้วลองใหม่");
  }
  if (res.status === 204) return undefined as T;
  const data = await res.json().catch(() => null);
  if (!res.ok) {
    let msg = (data && typeof data.detail === "string" && data.detail) || `เกิดข้อผิดพลาด (${res.status})`;
    if (data?.errors?.length) msg = `${msg}: ${data.errors.map((e: { message: string }) => e.message).join(", ")}`;
    throw new ApiError(res.status, msg, data);
  }
  return data as T;
}

export const api = {
  get: <T>(path: string) => request<T>("GET", path),
  post: <T>(path: string, body?: unknown) => request<T>("POST", path, body ?? {}),
  put: <T>(path: string, body?: unknown) => request<T>("PUT", path, body ?? {}),
  del: <T>(path: string) => request<T>("DELETE", path),
};

export const ACHIEVEMENT_TITLES: Record<string, string> = {
  first_query: "First Query",
  first_correct: "First Blood",
  sql_beginner: "SQL Beginner",
  beginner_graduate: "Beginner Graduate",
  join_master: "JOIN Master",
  subquery_expert: "Subquery Expert",
  window_master: "Window Function Master",
  data_builder: "Data Builder",
  streak_7: "7-Day Streak",
  sql_professional: "SQL Professional",
};
