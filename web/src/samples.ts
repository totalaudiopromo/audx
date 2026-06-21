/**
 * User sample store for the studio: drop your own audio onto a track and it plays
 * instead of the synth voice (CLI precedence: a resolvable sample wins, else the
 * built-in synth). Decoded with Web Audio, persisted as raw bytes in IndexedDB so
 * samples survive a reload. Share links carry only the sample *name/ref* — the audio
 * stays on each machine, exactly like the CLI's local sample library.
 *
 * The pure ref-hashing lives here too (testable); decodeAudioData + IndexedDB are
 * browser-only and guarded.
 */

export interface StoredSample {
  ref: string;
  name: string;
  bytes: ArrayBuffer;
  buffer: AudioBuffer | null; // decoded lazily / on load
}

const store = new Map<string, StoredSample>();

/** Content-address bytes → a stable ref (sha-256 hex, truncated). */
export async function refForBytes(bytes: ArrayBuffer): Promise<string> {
  const digest = await crypto.subtle.digest("SHA-256", bytes);
  const hex = [...new Uint8Array(digest)].map((b) => b.toString(16).padStart(2, "0")).join("");
  return hex.slice(0, 16);
}

export const hasSample = (ref: string): boolean => store.has(ref) && store.get(ref)!.buffer !== null;
export const getSample = (ref: string): StoredSample | undefined => store.get(ref);

/** Decoded stereo channels for the offline renderer, or null if unavailable. */
export function sampleStereo(ref: string): { left: Float32Array; right: Float32Array } | null {
  const buf = store.get(ref)?.buffer;
  if (!buf) return null;
  const left = buf.getChannelData(0);
  const right = buf.numberOfChannels > 1 ? buf.getChannelData(1) : left;
  return { left, right };
}

/** Decode + store a dropped file, returning its ref + display name. */
export async function putSample(file: File, ctx: AudioContext): Promise<{ ref: string; name: string }> {
  const bytes = await file.arrayBuffer();
  const ref = await refForBytes(bytes);
  if (!store.has(ref)) {
    const buffer = await ctx.decodeAudioData(bytes.slice(0));
    store.set(ref, { ref, name: file.name, bytes, buffer });
    void persist(ref);
  }
  return { ref, name: file.name };
}

// ── IndexedDB persistence ───────────────────────────────────────────────────────
const DB_NAME = "audx.studio";
const STORE = "samples";

function openDb(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, 1);
    req.onupgradeneeded = () => req.result.createObjectStore(STORE, { keyPath: "ref" });
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

async function persist(ref: string): Promise<void> {
  const s = store.get(ref);
  if (!s || typeof indexedDB === "undefined") return;
  try {
    const db = await openDb();
    const tx = db.transaction(STORE, "readwrite");
    tx.objectStore(STORE).put({ ref: s.ref, name: s.name, bytes: s.bytes });
  } catch { /* persistence is best-effort */ }
}

/** Re-load + decode every persisted sample on boot, so restored sessions resolve. */
export async function loadAllFromIDB(ctx: AudioContext): Promise<void> {
  if (typeof indexedDB === "undefined") return;
  try {
    const db = await openDb();
    const rows: { ref: string; name: string; bytes: ArrayBuffer }[] = await new Promise((res, rej) => {
      const req = db.transaction(STORE, "readonly").objectStore(STORE).getAll();
      req.onsuccess = () => res(req.result);
      req.onerror = () => rej(req.error);
    });
    for (const row of rows) {
      if (store.has(row.ref)) continue;
      try {
        const buffer = await ctx.decodeAudioData(row.bytes.slice(0));
        store.set(row.ref, { ...row, buffer });
      } catch { /* skip undecodable */ }
    }
  } catch { /* ignore */ }
}
