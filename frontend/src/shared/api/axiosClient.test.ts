import type { AxiosAdapter, AxiosResponse, InternalAxiosRequestConfig } from "axios";
import { AxiosError } from "axios";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { apiClient } from "./axiosClient";
import { authClient, setAccessToken, setAuthenticationFailureHandler } from "./authSession";

const EXPIRED_TOKEN = "expired-token";
const FRESH_TOKEN = "fresh-token";

function respond(config: InternalAxiosRequestConfig, status: number, data: unknown): Promise<AxiosResponse> {
  const response: AxiosResponse = { data, status, statusText: "", headers: {}, config };
  if (status >= 400) {
    return Promise.reject(new AxiosError("Request failed", String(status), config, null, response));
  }
  return Promise.resolve(response);
}

describe("apiClient token handling", () => {
  let refreshRequests: number;
  let attemptsByUrl: Record<string, number>;
  let refreshSucceeds: boolean;
  const onAuthenticationFailure = vi.fn();

  // The protected API accepts only the fresh token; the auth endpoints are served by authClient's adapter.
  const protectedApiAdapter: AxiosAdapter = (config) => {
    const url = config.url ?? "";
    attemptsByUrl[url] = (attemptsByUrl[url] ?? 0) + 1;
    const isFresh = config.headers.get("Authorization") === `Bearer ${FRESH_TOKEN}`;
    return isFresh ? respond(config, 200, { url }) : respond(config, 401, { error: { code: "NOT_AUTHENTICATED" } });
  };

  const authAdapter: AxiosAdapter = async (config) => {
    if (config.url === "/auth/csrf/") {
      return respond(config, 200, { csrf_token: "csrf" });
    }
    refreshRequests += 1;
    // Slow enough that concurrent callers overlap with the in-flight refresh.
    await new Promise((resolve) => setTimeout(resolve, 20));
    return refreshSucceeds
      ? respond(config, 200, { access: FRESH_TOKEN })
      : respond(config, 401, { error: { code: "NOT_AUTHENTICATED" } });
  };

  beforeEach(() => {
    refreshRequests = 0;
    attemptsByUrl = {};
    refreshSucceeds = true;
    onAuthenticationFailure.mockClear();
    setAccessToken(EXPIRED_TOKEN);
    setAuthenticationFailureHandler(onAuthenticationFailure);
    apiClient.defaults.adapter = protectedApiAdapter;
    authClient.defaults.adapter = authAdapter;
  });

  afterEach(() => {
    setAccessToken(null);
    setAuthenticationFailureHandler(() => {});
  });

  it("shares one refresh between concurrent 401s and retries each request once", async () => {
    const responses = await Promise.all([apiClient.get("/a"), apiClient.get("/b"), apiClient.get("/c")]);

    expect(responses.map((response) => response.status)).toEqual([200, 200, 200]);
    expect(refreshRequests).toBe(1);
    expect(attemptsByUrl).toEqual({ "/a": 2, "/b": 2, "/c": 2 });
    expect(onAuthenticationFailure).not.toHaveBeenCalled();
  });

  it("ends the session once when the refresh fails, without retrying the request", async () => {
    refreshSucceeds = false;

    await expect(apiClient.get("/a")).rejects.toMatchObject({ response: { status: 401 } });

    expect(refreshRequests).toBe(1);
    expect(attemptsByUrl["/a"]).toBe(1);
    expect(onAuthenticationFailure).toHaveBeenCalledTimes(1);
  });

  it("does not loop when the retried request is still unauthorized", async () => {
    apiClient.defaults.adapter = (config) => respond(config, 401, { error: { code: "NOT_AUTHENTICATED" } });

    await expect(apiClient.get("/a")).rejects.toMatchObject({ response: { status: 401 } });

    expect(refreshRequests).toBe(1);
    expect(onAuthenticationFailure).toHaveBeenCalledTimes(1);
  });

  it("retries a late 401 with the current token instead of refreshing again", async () => {
    // The first request is answered 401 only after a refresh has already replaced its token.
    setAccessToken(FRESH_TOKEN);
    let hasAnsweredLateUnauthorized = false;
    apiClient.defaults.adapter = (config) => {
      if (!hasAnsweredLateUnauthorized) {
        hasAnsweredLateUnauthorized = true;
        config.headers.set("Authorization", `Bearer ${EXPIRED_TOKEN}`);
        return respond(config, 401, {});
      }
      return respond(config, 200, {});
    };

    const response = await apiClient.get("/a");

    expect(response.status).toBe(200);
    expect(refreshRequests).toBe(0);
  });

  it("refreshes once when a request sent without any token is rejected", async () => {
    setAccessToken(null);

    const response = await apiClient.get("/a");

    // After the refresh the retry carries the new token, which the API accepts.
    expect(response.status).toBe(200);
    expect(refreshRequests).toBe(1);
    expect(attemptsByUrl["/a"]).toBe(2);
  });

  it("does not attach a Bearer header when there is no access token", async () => {
    setAccessToken(null);
    let sentAuthorization: unknown = "not-called";
    apiClient.defaults.adapter = (config) => {
      sentAuthorization = config.headers.get("Authorization");
      return respond(config, 200, {});
    };

    await apiClient.get("/public");

    expect(sentAuthorization).toBeUndefined();
  });
});
