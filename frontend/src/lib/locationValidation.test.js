import { describe, it, expect } from "vitest";

import {
  IRELAND_LAT_MAX,
  IRELAND_LAT_MIN,
  IRELAND_LON_MAX,
  validateIrelandLocation,
} from "./locationValidation.js";

describe("validateIrelandLocation", () => {
  it("returns null for non-numeric input (form not filled)", () => {
    expect(validateIrelandLocation("", "")).toBeNull();
    expect(validateIrelandLocation("abc", "def")).toBeNull();
  });

  it("accepts Dublin centre", () => {
    expect(validateIrelandLocation("53.3498", "-6.2603")).toBeNull();
  });

  it("rejects latitude below Ireland", () => {
    const msg = validateIrelandLocation("51.0", "-6.26");
    expect(msg).toContain("Latitude");
    expect(msg).toContain(String(IRELAND_LAT_MIN));
  });

  it("rejects longitude east of Ireland bound", () => {
    const msg = validateIrelandLocation("53.35", "-4.5");
    expect(msg).toContain("Longitude");
    expect(msg).toContain(String(IRELAND_LON_MAX));
  });

  it("accepts boundary latitude", () => {
    expect(validateIrelandLocation(String(IRELAND_LAT_MIN), "-8")).toBeNull();
    expect(validateIrelandLocation(String(IRELAND_LAT_MAX), "-8")).toBeNull();
  });
});
