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
