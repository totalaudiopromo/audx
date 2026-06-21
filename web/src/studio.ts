/**
 * audx studio — a browser drum machine powered by the native TypeScript synth.
 *
 * 16-step grid sequencer with a sample-accurate Web Audio lookahead scheduler,
 * per-track mute/solo/volume, swing, and one-click export to the audx DSL so a
 * groove built here drops straight into the CLI. No framework, no dependencies.
 */

import { SYNTH_VOICES, synthVoice, type Voice } from "./synth";
import {
  BAR_STEPS, VEL_ACCENT, VEL_GHOST, VEL_NORMAL, VEL_OFF,
  audibleTracks, resizeSteps, type ProjectState, type Track,
} from "./types";
import { decodeProject, encodeProject } from "./project";
import { renderProject, renderSong, renderStems, toWav } from "./render";
import { MidiBridge } from "./midi";
import { getSample, hasSample, loadAllFromIDB, putSample, sampleStereo } from "./samples";
import { makeZip } from "./zip";
import { cliToSong, songStepPlan, songToCli, type Scene, type Song } from "./song";

const SCHEDULE_AHEAD = 0.1; // seconds of lookahead
const TICK_MS = 25;
const ON_LEVELS = [VEL_GHOST, VEL_NORMAL, VEL_ACCENT];

interface Starter {
  voice: Voice;
  pattern: number[];
}

const STARTER: Starter[] = [
  { voice: "kick", pattern: [0, 4, 8, 12] },
  { voice: "clap", pattern: [4, 12] },
  { voice: "hh", pattern: [0, 2, 4, 6, 8, 10, 12, 14] },
  { voice: "bass", pattern: [0, 6, 8, 14] },
];

let nextId = 1;
function makeTrack(voice: Voice, hits: number[] = []): Track {
  const steps = new Array(BAR_STEPS * state.bars).fill(VEL_OFF);
  for (const h of hits) steps[h] = VEL_NORMAL;
  return { id: nextId++, voice, steps, mute: false, solo: false, gain: 0.9, pan: 0 };
}

const totalSteps = (): number => BAR_STEPS * state.bars;
const velClass = (v: number): string =>
  v >= VEL_ACCENT ? "accent" : v >= VEL_NORMAL ? "normal" : v > 0 ? "ghost" : "";

// ── state ───────────────────────────────────────────────────────────────────────
interface StudioState extends ProjectState {
  playing: boolean;
}
const state: StudioState = {
  tracks: [],
  bpm: 124,
  swing: 0,
  bars: 1,
  playing: false,
};
state.tracks = STARTER.map((s) => makeTrack(s.voice, s.pattern));

const STORAGE_KEY = "audx.studio.session";

function snapshot(): ProjectState {
  return { bpm: state.bpm, swing: state.swing, bars: state.bars, tracks: state.tracks };
}

function persist(): void {
  try { localStorage.setItem(STORAGE_KEY, encodeProject(snapshot())); } catch { /* ignore */ }
}

/** Load from the URL hash (a shared link) or localStorage, if present. */
function loadSaved(): void {
  const fromHash = location.hash.startsWith("#p=") ? decodeProject(location.hash.slice(3)) : null;
  const saved = fromHash ?? (() => {
    try { const s = localStorage.getItem(STORAGE_KEY); return s ? decodeProject(s) : null; }
    catch { return null; }
  })();
  if (saved && saved.tracks.length) {
    state.bpm = saved.bpm;
    state.swing = saved.swing;
    state.bars = saved.bars;
    state.tracks = saved.tracks;
    nextId = Math.max(0, ...state.tracks.map((t) => t.id)) + 1;
  }
}

// ── audio engine ──────────────────────────────────────────────────────────────
let ctx: AudioContext | null = null;
let master: GainNode;
let analyser: AnalyserNode;
const buffers = new Map<Voice, AudioBuffer>();
let currentStep = 0;
let nextStepTime = 0;
let timer: number | null = null;
type SongEntry = { scene: Scene; localStep: number };
let songPlan: SongEntry[] | null = null;
const playQueue: { step: number; time: number; song?: SongEntry }[] = [];

function ensureAudio(): AudioContext {
  if (ctx) return ctx;
  ctx = new (window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext)();
  master = ctx.createGain();
  master.gain.value = 0.9;
  analyser = ctx.createAnalyser();
  analyser.fftSize = 1024;
  master.connect(analyser);
  analyser.connect(ctx.destination);
  for (const v of SYNTH_VOICES) voiceBuffer(v);
  void loadAllFromIDB(ctx); // restore persisted samples for refs in this session
  return ctx;
}

function voiceBuffer(voice: Voice): AudioBuffer {
  let buf = buffers.get(voice);
  if (buf) return buf;
  const data = synthVoice(voice, ctx!.sampleRate);
  buf = ctx!.createBuffer(1, data.length, ctx!.sampleRate);
  buf.getChannelData(0).set(data);
  buffers.set(voice, buf);
  return buf;
}

function secondsPerStep(): number {
  return 60.0 / state.bpm / 4.0; // 16th notes
}

/** The AudioBuffer a track plays: its loaded sample if present, else the synth. */
function bufferForTrack(track: Track): AudioBuffer {
  if (track.sampleRef && hasSample(track.sampleRef)) {
    return getSample(track.sampleRef)!.buffer!;
  }
  return voiceBuffer(track.voice);
}

function auditionBuffer(buf: AudioBuffer): void {
  if (!ctx) return;
  const src = ctx.createBufferSource();
  src.buffer = buf;
  src.connect(master);
  src.start();
}

/** Play a single voice one-shot now (MIDI pads, by voice name). */
function audition(voice: Voice): void {
  if (ctx) auditionBuffer(voiceBuffer(voice));
}

const midi = new MidiBridge({
  onPad: (voice) => { ensureAudio(); audition(voice as Voice); },
  onTransport: (action) => { if (action === "play") play(); else stop(); },
});

/** Schedule one 16th-step's hits for the given tracks at audio time `time`. */
function scheduleHits(tracks: Track[], localStep: number, time: number, swing: number): void {
  const swingOffset = localStep % 2 === 1 ? secondsPerStep() * swing : 0;
  for (const track of audibleTracks(tracks)) {
    const vel = track.steps[localStep] ?? 0;
    if (vel <= 0) continue;
    const src = ctx!.createBufferSource();
    src.buffer = bufferForTrack(track);
    const g = ctx!.createGain();
    g.gain.value = track.gain * vel;
    src.connect(g);
    if (track.pan) {
      const pan = ctx!.createStereoPanner();
      pan.pan.value = Math.max(-1, Math.min(1, track.pan));
      g.connect(pan); pan.connect(master);
    } else {
      g.connect(master);
    }
    src.start(time + swingOffset);
  }
}

function scheduleStep(step: number, time: number): void {
  if (songPlan) {
    const entry = songPlan[step % songPlan.length];
    scheduleHits(entry.scene.tracks, entry.localStep, time, entry.scene.swing);
    playQueue.push({ step, time, song: entry });
  } else {
    scheduleHits(state.tracks, step, time, state.swing);
    const swingOffset = step % 2 === 1 ? secondsPerStep() * state.swing : 0;
    playQueue.push({ step, time: time + swingOffset });
  }
}

function transportSteps(): number {
  return songPlan ? songPlan.length : totalSteps();
}

function scheduler(): void {
  if (!ctx) return;
  while (nextStepTime < ctx.currentTime + SCHEDULE_AHEAD) {
    scheduleStep(currentStep, nextStepTime);
    nextStepTime += secondsPerStep();
    currentStep = (currentStep + 1) % transportSteps();
  }
}

function play(): void {
  const audio = ensureAudio();
  if (audio.state === "suspended") void audio.resume();
  state.playing = true;
  currentStep = 0;
  nextStepTime = audio.currentTime + 0.05;
  timer = window.setInterval(scheduler, TICK_MS);
  paintTransport();
  requestAnimationFrame(animate);
}

function stop(): void {
  state.playing = false;
  songPlan = null;
  if (timer !== null) { clearInterval(timer); timer = null; }
  playQueue.length = 0;
  document.querySelectorAll(".cell.playhead").forEach((el) => el.classList.remove("playhead"));
  document.querySelectorAll(".scene-chip.active").forEach((el) => el.classList.remove("active"));
  $("#song-status").textContent = "";
  paintTransport();
}

function togglePlay(): void {
  state.playing ? stop() : play();
}

// ── render UI ─────────────────────────────────────────────────────────────────
const $ = <T extends HTMLElement>(sel: string): T => document.querySelector(sel) as T;
const grid = $("#grid");
const meterFill = $("#meter-fill");
const escapeHtml = (s: string): string =>
  s.replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]!);

async function loadSampleFile(track: Track, file: File | undefined): Promise<void> {
  if (!file) return;
  ensureAudio();
  try {
    const { ref, name } = await putSample(file, ctx!);
    track.sampleRef = ref;
    track.sampleName = name;
    renderGrid(); persist();
  } catch { /* undecodable file — leave on the synth */ }
}

function renderGrid(): void {
  grid.innerHTML = "";
  for (const track of state.tracks) {
    const row = document.createElement("div");
    row.className = "row";
    row.dataset.id = String(track.id);

    const head = document.createElement("div");
    head.className = "track-head";
    head.innerHTML = `
      <select class="voice" aria-label="voice">
        ${SYNTH_VOICES.map((v) => `<option ${v === track.voice ? "selected" : ""}>${v}</option>`).join("")}
      </select>
      <div class="track-btns">
        <button class="mini mute ${track.mute ? "on" : ""}" title="mute">M</button>
        <button class="mini solo ${track.solo ? "on" : ""}" title="solo">S</button>
        <input class="vol" type="range" min="0" max="1.4" step="0.05" value="${track.gain}" title="volume" />
        <button class="mini del" title="remove">✕</button>
      </div>
      <input class="pan" type="range" min="-1" max="1" step="0.1" value="${track.pan}" title="pan (L–R)" />
      <div class="sample-line">
        <label class="sample-btn" title="load your own sample (or drop a file on this row)">📁<input class="sample-input" type="file" accept="audio/*" hidden /></label>
        <span class="sample-name ${track.sampleRef ? "has" : ""}">${track.sampleRef ? escapeHtml(track.sampleName ?? "sample") : "synth"}</span>
        ${track.sampleRef ? '<button class="mini clearsample" title="back to synth">×</button>' : ""}
      </div>`;
    row.appendChild(head);

    const cells = document.createElement("div");
    cells.className = "cells";
    cells.style.gridTemplateColumns = `repeat(${totalSteps()}, 1fr)`;
    for (let i = 0; i < totalSteps(); i++) {
      const cell = document.createElement("button");
      const on = track.steps[i] > 0;
      cell.className = `cell ${on ? "on " + velClass(track.steps[i]) : ""} ${i % 4 === 0 ? "downbeat" : ""} ${i % BAR_STEPS === 0 && i > 0 ? "barline" : ""}`;
      cell.dataset.step = String(i);
      cells.appendChild(cell);
    }
    row.appendChild(cells);
    grid.appendChild(row);
  }
}

function trackById(id: number): Track | undefined {
  return state.tracks.find((t) => t.id === id);
}

function paintCell(cell: HTMLElement, track: Track, step: number, value: number): void {
  track.steps[step] = value;
  cell.className = `cell ${value > 0 ? "on " + velClass(value) : ""} ${step % 4 === 0 ? "downbeat" : ""} ${step % BAR_STEPS === 0 && step > 0 ? "barline" : ""}`;
}
function cellCtx(e: Event): { cell: HTMLElement; track: Track; step: number } | null {
  const cell = (e.target as HTMLElement).closest(".cell") as HTMLElement | null;
  if (!cell) return null;
  const track = trackById(Number((cell.closest(".row") as HTMLElement).dataset.id));
  if (!track) return null;
  return { cell, track, step: Number(cell.dataset.step) };
}

// event delegation on the grid
let painting: number | null = null; // the velocity we're painting (0 = erasing)
grid.addEventListener("pointerdown", (e) => {
  if ((e as PointerEvent).button === 2) return; // right-click handled below
  const c = cellCtx(e);
  if (!c) return;
  painting = c.track.steps[c.step] > 0 ? VEL_OFF : VEL_NORMAL;
  paintCell(c.cell, c.track, c.step, painting);
  if (painting > 0) auditionBuffer(bufferForTrack(c.track));
});
grid.addEventListener("pointerover", (e) => {
  if (painting === null) return;
  const c = cellCtx(e);
  if (c) paintCell(c.cell, c.track, c.step, painting);
});
window.addEventListener("pointerup", () => { if (painting !== null) persist(); painting = null; });

// right-click an on-cell to cycle ghost → normal → accent
grid.addEventListener("contextmenu", (e) => {
  const c = cellCtx(e);
  if (!c) return;
  e.preventDefault();
  if (c.track.steps[c.step] <= 0) { paintCell(c.cell, c.track, c.step, VEL_GHOST); }
  else {
    const idx = ON_LEVELS.findIndex((l) => Math.abs(l - c.track.steps[c.step]) < 1e-6);
    paintCell(c.cell, c.track, c.step, ON_LEVELS[(idx + 1) % ON_LEVELS.length]);
  }
  auditionBuffer(bufferForTrack(c.track));
  persist();
});

grid.addEventListener("change", (e) => {
  const el = e.target as HTMLElement;
  const row = el.closest(".row") as HTMLElement;
  const track = trackById(Number(row.dataset.id));
  if (!track) return;
  if (el.classList.contains("voice")) track.voice = (el as HTMLSelectElement).value as Voice;
  if (el.classList.contains("vol")) track.gain = Number((el as HTMLInputElement).value);
  if (el.classList.contains("pan")) track.pan = Number((el as HTMLInputElement).value);
  if (el.classList.contains("sample-input")) { void loadSampleFile(track, (el as HTMLInputElement).files?.[0]); return; }
  persist();
});

// drag a file onto a track row to load it as that track's sample
grid.addEventListener("dragover", (e) => {
  if (!(e as DragEvent).dataTransfer?.types.includes("Files")) return;
  e.preventDefault();
  (e.target as HTMLElement).closest(".row")?.classList.add("dragover");
});
grid.addEventListener("dragleave", (e) => {
  (e.target as HTMLElement).closest(".row")?.classList.remove("dragover");
});
grid.addEventListener("drop", (e) => {
  const row = (e.target as HTMLElement).closest(".row") as HTMLElement | null;
  if (!row) return;
  e.preventDefault();
  row.classList.remove("dragover");
  const track = trackById(Number(row.dataset.id));
  if (track) void loadSampleFile(track, (e as DragEvent).dataTransfer?.files?.[0]);
});
grid.addEventListener("click", (e) => {
  const btn = (e.target as HTMLElement).closest("button.mini") as HTMLElement | null;
  if (!btn) return;
  const row = btn.closest(".row") as HTMLElement;
  const track = trackById(Number(row.dataset.id));
  if (!track) return;
  if (btn.classList.contains("mute")) { track.mute = !track.mute; btn.classList.toggle("on", track.mute); }
  else if (btn.classList.contains("solo")) { track.solo = !track.solo; btn.classList.toggle("on", track.solo); }
  else if (btn.classList.contains("clearsample")) { delete track.sampleRef; delete track.sampleName; renderGrid(); }
  else if (btn.classList.contains("del")) { state.tracks = state.tracks.filter((t) => t.id !== track.id); renderGrid(); }
  persist();
});

// ── transport + toolbar ───────────────────────────────────────────────────────
function paintTransport(): void {
  $("#play").textContent = state.playing ? "■ stop" : "▶ play";
  $("#play").classList.toggle("playing", state.playing);
}

function animate(): void {
  if (!state.playing || !ctx) return;
  const now = ctx.currentTime;
  while (playQueue.length && playQueue[0].time <= now) {
    const { step, song } = playQueue.shift()!;
    document.querySelectorAll(".cell.playhead").forEach((el) => el.classList.remove("playhead"));
    if (song) {
      // song transport: show progress on the sequence, flash the active scene's hits
      highlightActiveScene(song.scene, step);
      for (const track of audibleTracks(song.scene.tracks)) {
        if (track.steps[song.localStep] > 0) midi.flashVoice(track.voice);
      }
    } else {
      document.querySelectorAll(`.cell[data-step="${step}"]`).forEach((el) => el.classList.add("playhead"));
      for (const track of audibleTracks(state.tracks)) {
        if (track.steps[step] > 0) midi.flashVoice(track.voice);
      }
    }
  }
  midi.tick();
  // master meter
  if (analyser) {
    const buf = new Float32Array(analyser.fftSize);
    analyser.getFloatTimeDomainData(buf);
    let sum = 0;
    for (let i = 0; i < buf.length; i++) sum += buf[i] * buf[i];
    const rms = Math.sqrt(sum / buf.length);
    meterFill.style.width = `${Math.min(100, rms * 180)}%`;
  }
  requestAnimationFrame(animate);
}

function toDSL(): string {
  return state.tracks
    .map((t) => {
      const grid = t.steps.map((s) => (s > 0 ? "1" : "0")).join("");
      const mods = t.mute ? " | vel 0" : "";
      return `${t.voice} [${grid}]${mods}`;
    })
    .join("\n");
}

function wireToolbar(): void {
  $("#play").addEventListener("click", togglePlay);
  $("#clear").addEventListener("click", () => {
    state.tracks.forEach((t) => t.steps.fill(VEL_OFF));
    renderGrid(); persist();
  });

  const bars = $<HTMLSelectElement>("#bars");
  bars.addEventListener("change", () => {
    state.bars = Number(bars.value);
    for (const t of state.tracks) t.steps = resizeSteps(t.steps, totalSteps());
    renderGrid(); persist();
  });
  $("#add").addEventListener("click", () => {
    const used = new Set(state.tracks.map((t) => t.voice));
    const next = SYNTH_VOICES.find((v) => !used.has(v)) ?? "kick";
    state.tracks.push(makeTrack(next));
    renderGrid(); persist();
  });

  const bpm = $<HTMLInputElement>("#bpm");
  const bpmVal = $("#bpm-val");
  bpm.addEventListener("input", () => { state.bpm = Number(bpm.value); bpmVal.textContent = bpm.value; persist(); });

  const swing = $<HTMLInputElement>("#swing");
  const swingVal = $("#swing-val");
  swing.addEventListener("input", () => {
    state.swing = Number(swing.value) / 100;
    swingVal.textContent = `${swing.value}%`;
    persist();
  });

  $("#share").addEventListener("click", async () => {
    const url = `${location.origin}${location.pathname}#p=${encodeProject(snapshot())}`;
    history.replaceState(null, "", url);
    try { await navigator.clipboard.writeText(url); $("#share").textContent = "link copied ✓"; }
    catch { $("#share").textContent = "link in address bar"; }
    setTimeout(() => ($("#share").textContent = "share link"), 1600);
  });

  $("#wav").addEventListener("click", () => {
    ensureAudio();
    download(toWav(renderProject(snapshot(), 2, ctx!.sampleRate, sampleStereo)), "audx-studio.wav", "audio/wav");
  });

  $("#stems").addEventListener("click", () => {
    ensureAudio();
    const stems = renderStems(snapshot(), 2, ctx!.sampleRate, sampleStereo);
    if (!stems.length) return;
    download(makeZip(stems.map((s) => ({ name: s.name, data: s.wav }))), "audx-stems.zip", "application/zip");
  });

  $("#export").addEventListener("click", async () => {
    const dsl = toDSL();
    const out = $("#dsl-out");
    out.textContent = dsl;
    out.classList.add("show");
    try { await navigator.clipboard.writeText(dsl); $("#export").textContent = "copied ✓"; }
    catch { $("#export").textContent = "copy as audx DSL"; }
    setTimeout(() => ($("#export").textContent = "copy as audx DSL"), 1600);
  });

  const midiBtn = $("#midi");
  const midiStatus = $("#midi-status");
  if (!midi.supported) { midiBtn.style.display = "none"; }
  midiBtn.addEventListener("click", async () => {
    ensureAudio();
    midiStatus.textContent = "connecting…";
    try {
      midiStatus.textContent = await midi.connect();
      midiBtn.classList.add("on");
    } catch (err) {
      midiStatus.textContent = err instanceof Error ? err.message : "MIDI failed";
    }
  });

  document.addEventListener("keydown", (e) => {
    if (e.code === "Space" && !(e.target as HTMLElement).matches("input,select,textarea")) {
      e.preventDefault();
      togglePlay();
    }
  });
}

function download(bytes: Uint8Array, name: string, type: string): void {
  const url = URL.createObjectURL(new Blob([bytes.buffer as ArrayBuffer], { type }));
  const a = document.createElement("a");
  a.href = url; a.download = name; a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

// ── song mode ──────────────────────────────────────────────────────────────────
const SONG_KEY = "audx.studio.song";
const song: Song = { bpm: 124, scenes: [], sequence: [] };

/** Live song transport feedback: light the active scene/sequence chip + readout. */
function highlightActiveScene(scene: Scene, globalStep: number): void {
  document.querySelectorAll(".scene-chip").forEach((el) =>
    el.classList.toggle("active", (el as HTMLElement).dataset.scene === scene.name));
  const bar = Math.floor(globalStep / BAR_STEPS);
  const totalB = songPlan ? songPlan.length / BAR_STEPS : 0;
  let acc = 0;
  let seqIdx = -1;
  for (let i = 0; i < song.sequence.length; i++) {
    const b = song.scenes.find((s) => s.name === song.sequence[i])?.bars ?? 0;
    if (bar < acc + b) { seqIdx = i; break; }
    acc += b;
  }
  const seqChips = document.querySelectorAll("#seq-chips .seq-chip");
  seqChips.forEach((el, i) => el.classList.toggle("active", i === seqIdx));
  $("#song-status").textContent = `▶ ${scene.name} · bar ${bar + 1}/${totalB}`;
}

function persistSong(): void {
  try { localStorage.setItem(SONG_KEY, JSON.stringify(songToCli(song))); } catch { /* ignore */ }
}
function loadSong(): void {
  try {
    const raw = localStorage.getItem(SONG_KEY);
    if (!raw) return;
    const loaded = cliToSong(JSON.parse(raw));
    song.scenes = loaded.scenes;
    song.sequence = loaded.sequence;
  } catch { /* ignore */ }
}

function renderSongChips(): void {
  const scenes = $("#scene-chips");
  const seq = $("#seq-chips");
  scenes.innerHTML = "";
  for (const scene of song.scenes) {
    const chip = document.createElement("button");
    chip.className = "scene-chip";
    chip.dataset.scene = scene.name;
    chip.textContent = `${scene.name} · ${scene.bars}b`;
    chip.title = "click: add to sequence · shift-click: load into the grid";
    chip.onclick = (e) => {
      if (e.shiftKey) { loadScene(scene); return; }
      song.sequence.push(scene.name); renderSongChips(); persistSong();
    };
    scenes.appendChild(chip);
  }
  seq.innerHTML = "";
  song.sequence.forEach((name, i) => {
    const chip = document.createElement("button");
    chip.className = "seq-chip";
    chip.textContent = `${i + 1}. ${name} ✕`;
    chip.title = "remove from sequence";
    chip.onclick = () => { song.sequence.splice(i, 1); renderSongChips(); persistSong(); };
    seq.appendChild(chip);
  });
}

function loadScene(scene: Scene): void {
  state.bars = scene.bars;
  state.swing = scene.swing;
  state.tracks = structuredClone(scene.tracks);
  nextId = Math.max(0, ...state.tracks.map((t) => t.id)) + 1;
  renderGrid(); syncTransportInputs(); persist();
}

function wireSong(): void {
  loadSong();
  renderSongChips();

  $("#save-scene").addEventListener("click", () => {
    const name = prompt("Scene name:", `scene ${song.scenes.length + 1}`)?.trim();
    if (!name) return;
    const scene: Scene = { name, bars: state.bars, swing: state.swing, tracks: structuredClone(state.tracks) };
    const at = song.scenes.findIndex((s) => s.name === name);
    if (at >= 0) song.scenes[at] = scene; else song.scenes.push(scene);
    renderSongChips(); persistSong();
  });

  $("#song-play").addEventListener("click", () => {
    if (!song.sequence.length) { $("#song-status").textContent = "add scenes to the sequence first"; return; }
    song.bpm = state.bpm;
    const plan = songStepPlan(song);
    if (!plan.length) return;
    stop(); // stop any pattern playback first
    songPlan = plan;
    play(); // drives the live scheduler across the song timeline (loops)
  });
  $("#song-stop").addEventListener("click", () => stop());

  $("#song-wav").addEventListener("click", () => {
    if (!song.sequence.length) return;
    ensureAudio();
    song.bpm = state.bpm;
    download(toWav(renderSong(song, ctx!.sampleRate, sampleStereo)), "audx-song.wav", "audio/wav");
  });

  $("#song-export").addEventListener("click", () => {
    song.bpm = state.bpm;
    const json = JSON.stringify(songToCli(song), null, 2);
    download(new TextEncoder().encode(json), "audx-song.json", "application/json");
  });

  $<HTMLInputElement>("#song-import").addEventListener("change", async (e) => {
    const file = (e.target as HTMLInputElement).files?.[0];
    if (!file) return;
    try {
      const loaded = cliToSong(JSON.parse(await file.text()));
      song.scenes = loaded.scenes; song.sequence = loaded.sequence; song.bpm = loaded.bpm;
      renderSongChips(); persistSong();
      $("#song-status").textContent = `imported ${song.scenes.length} scenes`;
    } catch { $("#song-status").textContent = "couldn't read that JSON"; }
  });
}

function syncTransportInputs(): void {
  const bpm = $<HTMLInputElement>("#bpm");
  const swing = $<HTMLInputElement>("#swing");
  bpm.value = String(state.bpm);
  $("#bpm-val").textContent = String(state.bpm);
  swing.value = String(Math.round(state.swing * 100));
  $("#swing-val").textContent = `${Math.round(state.swing * 100)}%`;
  $<HTMLSelectElement>("#bars").value = String(state.bars);
}

loadSaved();
renderGrid();
wireToolbar();
wireSong();
syncTransportInputs();
paintTransport();
