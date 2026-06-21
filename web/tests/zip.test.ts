import { describe, expect, it } from "vitest";
import { crc32, makeZip } from "../src/zip";

describe("crc32", () => {
  it("matches the known CRC32 of 'IEND' bytes / a reference vector", () => {
    // CRC32("123456789") = 0xCBF43926, the canonical check value.
    expect(crc32(new TextEncoder().encode("123456789")) >>> 0).toBe(0xcbf43926);
  });
});

describe("makeZip (store-only)", () => {
  const enc = new TextEncoder();
  const entries = [
    { name: "01-kick.wav", data: enc.encode("hello kick") },
    { name: "02-hh.wav", data: enc.encode("hat data here") },
  ];
  const zip = makeZip(entries);

  it("starts with the local-file-header signature and ends with EOCD", () => {
    const dv = new DataView(zip.buffer);
    expect(dv.getUint32(0, true)).toBe(0x04034b50); // first local header
    expect(dv.getUint32(zip.length - 22, true)).toBe(0x06054b50); // EOCD
    expect(dv.getUint16(zip.length - 22 + 10, true)).toBe(2); // total entries
  });

  it("stores entries uncompressed and recoverable", () => {
    // method 0 (store): the raw data sits right after the 30+namelen header.
    const nameLen = entries[0].name.length;
    const dataStart = 30 + nameLen;
    const stored = zip.slice(dataStart, dataStart + entries[0].data.length);
    expect(new TextDecoder().decode(stored)).toBe("hello kick");
  });

  it("declares method 0 (no compression)", () => {
    const dv = new DataView(zip.buffer);
    expect(dv.getUint16(8, true)).toBe(0); // compression method on first entry
  });
});
