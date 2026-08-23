"use client";

import { useEffect, useState } from "react";

type ApiStatus = "loading" | "ok" | "err";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export default function Home() {
  const [status, setStatus] = useState<ApiStatus>("loading");
  const [detail, setDetail] = useState<string>("");

  useEffect(() => {
    let cancelled = false;

    async function check() {
      try {
        const res = await fetch(`${API_BASE_URL}/health/ready`, {
          cache: "no-store",
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const body = (await res.json()) as { status?: string };
        if (cancelled) return;
        setStatus("ok");
        setDetail(body.status ?? "ready");
      } catch (err) {
        if (cancelled) return;
        setStatus("err");
        setDetail(err instanceof Error ? err.message : "unreachable");
      }
    }

    void check();
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <main>
      <h1>AI Video Director</h1>
      <p>Phase 0 foundation. Web and API health check.</p>
      <p>
        API status:{" "}
        <span className={`status ${status}`}>
          {status === "loading" && "checking…"}
          {status === "ok" && `ready (${detail})`}
          {status === "err" && `unreachable (${detail})`}
        </span>
      </p>
    </main>
  );
}
