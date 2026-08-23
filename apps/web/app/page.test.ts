import { describe, it, expect } from "vitest";

describe("health check helper", () => {
  it("resolves the API base URL from the environment", () => {
    const base = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
    expect(base).toMatch(/^https?:\/\//);
  });
});
