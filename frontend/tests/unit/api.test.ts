import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError, api } from "../../src/lib/api";

const BASE = "http://localhost:8000/v1";

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

  it("raises the demo banner flag from the response header", async () => {
    mockFetch(
      new Response(
        JSON.stringify({ lat: 28.6, lon: 77.2 }),
        { status: 200, headers: { "content-type": "application/json", "x-dhuan-demo": "1" } },
      ),
    );
    document.documentElement.dataset.demo = "0";
    await api.status();
    expect(document.documentElement.dataset.demo).toBe("1");
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
