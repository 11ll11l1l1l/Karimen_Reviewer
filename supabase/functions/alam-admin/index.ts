import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import { createClient } from "npm:@supabase/supabase-js@2";

// SHA-256 of a high-entropy admin password. The plaintext password is never stored
// in GitHub, Supabase tables, or Streamlit secrets.
const ADMIN_PASSWORD_SHA256 = "1252f3d1f8c24ed7fff1e5e28a8b5779d20723b657382ef7d18d86a02047d0fc";
const encoder = new TextEncoder();

async function sha256Hex(value: string): Promise<string> {
  const digest = await crypto.subtle.digest("SHA-256", encoder.encode(value));
  return Array.from(new Uint8Array(digest)).map((b) => b.toString(16).padStart(2, "0")).join("");
}

function constantTimeEqual(a: string, b: string): boolean {
  if (a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return diff === 0;
}

function json(status: number, payload: unknown): Response {
  return new Response(JSON.stringify(payload), {
    status,
    headers: {
      "content-type": "application/json; charset=utf-8",
      "cache-control": "no-store, private",
      "x-content-type-options": "nosniff",
    },
  });
}

function adminKey(): string {
  const secretKeys = Deno.env.get("SUPABASE_SECRET_KEYS");
  if (secretKeys) {
    try {
      const parsed = JSON.parse(secretKeys);
      if (typeof parsed?.default === "string" && parsed.default) return parsed.default;
    } catch {
      // Fall through to legacy key support while migration is still allowed.
    }
  }
  return Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") ?? "";
}

Deno.serve(async (req: Request) => {
  if (req.method !== "POST") return json(405, { ok: false, error: "method_not_allowed" });

  let body: Record<string, unknown>;
  try {
    body = await req.json();
  } catch {
    return json(400, { ok: false, error: "bad_request" });
  }

  const password = typeof body.password === "string" ? body.password : "";
  if (!password || password.length > 128) return json(401, { ok: false, error: "unauthorized" });

  const suppliedHash = await sha256Hex(password);
  if (!constantTimeEqual(suppliedHash, ADMIN_PASSWORD_SHA256)) {
    return json(401, { ok: false, error: "unauthorized" });
  }

  const supabaseUrl = Deno.env.get("SUPABASE_URL") ?? "";
  const secretKey = adminKey();
  if (!supabaseUrl || !secretKey) return json(503, { ok: false, error: "admin_backend_unavailable" });

  const client = createClient(supabaseUrl, secretKey, {
    auth: { persistSession: false, autoRefreshToken: false },
  });
  const { data, error } = await client.rpc("alam_admin_dashboard");
  if (error) {
    console.error("alam-admin dashboard rpc failed", error.code, error.message);
    return json(500, { ok: false, error: "dashboard_query_failed" });
  }

  return json(200, { ok: true, data });
});
