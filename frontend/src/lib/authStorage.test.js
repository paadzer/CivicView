import { describe, it, expect, beforeEach } from "vitest";

import {
  AUTH_TOKEN_KEY,
  AUTH_USER_KEY,
  getStoredToken,
  getStoredUser,
  setAuthToken,
} from "./authStorage.js";

describe("authStorage", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it("setAuthToken stores token and optional username", () => {
    setAuthToken("tok123", "alice");
    expect(localStorage.getItem(AUTH_TOKEN_KEY)).toBe("tok123");
    expect(localStorage.getItem(AUTH_USER_KEY)).toBe("alice");
  });

  it("setAuthToken(null) clears storage", () => {
    setAuthToken("x", "u");
    setAuthToken(null);
    expect(localStorage.getItem(AUTH_TOKEN_KEY)).toBeNull();
    expect(localStorage.getItem(AUTH_USER_KEY)).toBeNull();
  });

  it("getStoredToken and getStoredUser read back values", () => {
    localStorage.setItem(AUTH_TOKEN_KEY, "abc");
    localStorage.setItem(AUTH_USER_KEY, "bob");
    expect(getStoredToken()).toBe("abc");
    expect(getStoredUser()).toBe("bob");
  });
});
