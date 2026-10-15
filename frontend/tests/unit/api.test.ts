import { afterEach, describe, expect, it, vi } from "vitest";
import { API_BASE, ApiError, api } from "../../src/lib/api";

// Derive the expectation from the module itself. Hardcoding the host meant this
// test silently depended on a local .env that is gitignored, so it broke for
// anyone who did not have it.
const BASE = API_BASE;

function mockFetch(response: Response) {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response));
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("api client", () => {
  it("parses problem+json errors into ApiError", async () => {
    mockFetch(
      new Response(
        JSON.stringify({
          type: "https://x/problems/outside-coverage",
          title: "Point outside coverage",
          status: 422,
          detail: "not in Delhi-NCR",
          correlation_id: "abc",
        }),
        { status: 422, headers: { "content-type": "application/problem+json" } },
      ),
    );
    const err = await api.estimate(19.076, 72.877).catch((e) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect((err as ApiError).problem.title).toBe("Point outside coverage");
    expect((err as ApiError).status).toBe(422);
  });


  it("survives non-problem error bodies", async () => {
    mockFetch(
      new Response("gateway timeout", {
        status: 504,
        headers: { "content-type": "text/plain" },
      }),
    );
    const err = await api.status().catch((e) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect((err as ApiError).status).toBe(504);
  });

  it("POSTs explain with a JSON body", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ attribution: {}, advice: [] }), {
        status: 200,
        headers: { "content-type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);
    await api.explain(28.6, 77.2);
    expect(fetchMock).toHaveBeenCalledWith(
      `${BASE}/explain`,
      expect.objectContaining({ method: "POST" }),
    );
  });
});

describe("base64-wrapped problem responses", () => {
  // API Gateway returns successes as plain JSON but base64-encodes problem
  // responses. res.json() then threw "Unexpected token 'e', eyJ..." and the
  // reader saw a parse error instead of the API's actual message, which is the
  // one thing worth showing them.
  const problem = {
    type: "https://api.dhuan-detective.example/problems/validation",
    title: "Request validation failed",
    status: 422,
    detail: "from_lat is required.",
  };

  it("decodes a base64 problem body and surfaces its detail", async () => {
    const encoded = btoa(JSON.stringify(problem));
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(encoded, {
        status: 422,
        headers: { "content-type": "application/problem+json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await expect(api.compareRoutes({
      fromLat: 0, fromLon: 0, toLat: 0, toLon: 0,
    })).rejects.toThrowError(/from_lat is required/);
    vi.unstubAllGlobals();
  });

  it("still parses a plain problem body", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(problem), {
        status: 422,
        headers: { "content-type": "application/problem+json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await expect(api.compareRoutes({
      fromLat: 0, fromLon: 0, toLat: 0, toLon: 0,
    })).rejects.toThrowError(/from_lat is required/);
    vi.unstubAllGlobals();
  });

  it("reports unreadable bodies instead of a bare parse error", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response("<html>502</html>", {
        status: 422,
        headers: { "content-type": "application/problem+json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await expect(api.compareRoutes({
      fromLat: 0, fromLon: 0, toLat: 0, toLon: 0,
    })).rejects.toThrowError(/502/);
    vi.unstubAllGlobals();
  });
});

describe("compareRoutes URL", () => {
  // Regression: compareRoutes was the one caller using requestAt, whose base is
  // BASE_PATH with no /v1 segment. It requested /staging/routes/compare, which
  // the SPA catch-all answered with 405 Method Not Allowed - and because problem
  // bodies arrive base64-wrapped, the page showed a JSON parse error instead.
  it("includes the /v1 prefix every other endpoint uses", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ corridors: [] }), {
        status: 200,
        headers: { "content-type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await api.compareRoutes({ fromLat: 28.6, fromLon: 77.2, toLat: 28.7, toLon: 77.1 });

    const url = String(fetchMock.mock.calls[0]![0]);
    expect(url).toContain("/v1/routes/compare");
    vi.unstubAllGlobals();
  });

  it("sends the route payload the API documents", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ corridors: [] }), {
        status: 200,
        headers: { "content-type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await api.compareRoutes({ fromLat: 28.6, fromLon: 77.2, toLat: 28.7, toLon: 77.1 });

    const body = JSON.parse(String(fetchMock.mock.calls[0]![1]?.body ?? "{}"));
    expect(body).toMatchObject({ from_lat: 28.6, to_lon: 77.1 });
    vi.unstubAllGlobals();
  });
});
