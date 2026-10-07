// All backend calls go through the Vite proxy (/api -> FastAPI). No API keys live in the browser.
export const auth = { get: () => localStorage.getItem("cl_token"), set: (t) => localStorage.setItem("cl_token", t), clear: () => localStorage.removeItem("cl_token") };
export async function api(path, body, method) {
  const res = await fetch("/api" + path, {
    method: method || (body ? "POST" : "GET"),
    headers: { "Content-Type": "application/json", ...(auth.get() ? { Authorization: "Bearer " + auth.get() } : {}) },
    body: body ? JSON.stringify(body) : undefined,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    if (res.status === 401 && auth.get()) { auth.clear(); }
    if (typeof data.detail === "string") throw new Error(data.detail);
    if (Array.isArray(data.detail)) {
      const issues = data.detail.map((issue) => {
        const field = Array.isArray(issue.loc) ? issue.loc.filter((part) => part !== "body").join(" → ") : "Input";
        return `${field || "Input"}: ${issue.msg || "is invalid"}`;
      });
      throw new Error(issues.join("; "));
    }
    if (res.status >= 500) throw new Error(`The server could not complete this request (${res.status}). Please try again.`);
    throw new Error("Please check your input and try again.");
  }
  return data;
}
