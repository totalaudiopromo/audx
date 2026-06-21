/**
 * audx studio — a browser drum machine powered by the native TypeScript synth.
 *
 * 16-step grid sequencer with a sample-accurate Web Audio lookahead scheduler,
 * per-track mute/solo/volume, swing, and one-click export to the audx DSL so a
 * groove built here drops straight into the CLI. No framework, no dependencies.
 */

import { SYNTH_VOICES, synthVoice, type Voice } from "./synth";
import { STEPS, audibleTracks, type ProjectState, type Track } from "./types";
import { decodeProject, encodeProject } from "./project";
import { renderProject, toWav } from "./render";

const SCHEDULE_AHEAD = 0.1; // seconds of lookahead
const TICK_MS = 25;

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
  const steps = new Array(STEPS).fill(false);
  for (const h of hits) steps[h] = true;
  return { id: nextId++, voice, steps, mute: false, solo: false, gain: 0.9 };
}

// ── state ───────────────────────────────────────────────────────────────────────
interface StudioState extends ProjectState {
  playing: boolean;
}
const state: StudioState = {
  tracks: STARTER.map((s) => makeTrack(s.voice, s.pattern)),
  bpm: 124,
  swing: 0,
  playing: false,
};

const STORAGE_KEY = "audx.studio.session";

function snapshot(): ProjectState {
  return { bpm: state.bpm, swing: state.swing, tracks: state.tracks };
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
const playQueue: { step: number; time: number }[] = [];

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

function scheduleStep(step: number, time: number): void {
  const audible = audibleTracks(state.tracks);
  const swingOffset = step % 2 === 1 ? secondsPerStep() * state.swing : 0;
  for (const track of audible) {
    if (!track.steps[step]) continue;
    const src = ctx!.createBufferSource();
    src.buffer = voiceBuffer(track.voice);
    const g = ctx!.createGain();
    g.gain.value = track.gain;
    src.connect(g);
    g.connect(master);
    src.start(time + swingOffset);
  }
  playQueue.push({ step, time: time + swingOffset });
}

function scheduler(): void {
  if (!ctx) return;
  while (nextStepTime < ctx.currentTime + SCHEDULE_AHEAD) {
    scheduleStep(currentStep, nextStepTime);
    nextStepTime += secondsPerStep();
    currentStep = (currentStep + 1) % STEPS;
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
  if (timer !== null) { clearInterval(timer); timer = null; }
  playQueue.length = 0;
  document.querySelectorAll(".cell.playhead").forEach((el) => el.classList.remove("playhead"));
  paintTransport();
}

function togglePlay(): void {
  state.playing ? stop() : play();
}

// ── render UI ─────────────────────────────────────────────────────────────────
const $ = <T extends HTMLElement>(sel: string): T => document.querySelector(sel) as T;
const grid = $("#grid");
const meterFill = $("#meter-fill");

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
      </div>`;
    row.appendChild(head);

    const cells = document.createElement("div");
    cells.className = "cells";
    for (let i = 0; i < STEPS; i++) {
      const cell = document.createElement("button");
      cell.className = `cell ${track.steps[i] ? "on" : ""} ${i % 4 === 0 ? "downbeat" : ""}`;
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

// event delegation on the grid
let painting: boolean | null = null;
grid.addEventListener("pointerdown", (e) => {
  const cell = (e.target as HTMLElement).closest(".cell") as HTMLElement | null;
  if (!cell) return;
  const id = Number((cell.closest(".row") as HTMLElement).dataset.id);
  const step = Number(cell.dataset.step);
  const track = trackById(id);
  if (!track) return;
  painting = !track.steps[step];
  track.steps[step] = painting;
  cell.classList.toggle("on", painting);
  if (painting && ctx) {
    // audition the hit
    const src = ctx.createBufferSource();
    src.buffer = voiceBuffer(track.voice);
    src.connect(master);
    src.start();
  }
});
grid.addEventListener("pointerover", (e) => {
  if (painting === null) return;
  const cell = (e.target as HTMLElement).closest(".cell") as HTMLElement | null;
  if (!cell) return;
  const id = Number((cell.closest(".row") as HTMLElement).dataset.id);
  const step = Number(cell.dataset.step);
  const track = trackById(id);
  if (!track) return;
  track.steps[step] = painting;
  cell.classList.toggle("on", painting);
});
window.addEventListener("pointerup", () => { if (painting !== null) persist(); painting = null; });

grid.addEventListener("change", (e) => {
  const el = e.target as HTMLElement;
  const row = el.closest(".row") as HTMLElement;
  const track = trackById(Number(row.dataset.id));
  if (!track) return;
  if (el.classList.contains("voice")) track.voice = (el as HTMLSelectElement).value as Voice;
  if (el.classList.contains("vol")) track.gain = Number((el as HTMLInputElement).value);
  persist();
});
grid.addEventListener("click", (e) => {
  const btn = (e.target as HTMLElement).closest("button.mini") as HTMLElement | null;
  if (!btn) return;
  const row = btn.closest(".row") as HTMLElement;
  const track = trackById(Number(row.dataset.id));
  if (!track) return;
  if (btn.classList.contains("mute")) { track.mute = !track.mute; btn.classList.toggle("on", track.mute); }
  else if (btn.classList.contains("solo")) { track.solo = !track.solo; btn.classList.toggle("on", track.solo); }
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
    const { step } = playQueue.shift()!;
    document.querySelectorAll(".cell.playhead").forEach((el) => el.classList.remove("playhead"));
    document.querySelectorAll(`.cell[data-step="${step}"]`).forEach((el) => el.classList.add("playhead"));
  }
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
      const grid = t.steps.map((s) => (s ? "1" : "0")).join("");
      const mods = t.mute ? " | vel 0" : "";
      return `${t.voice} [${grid}]${mods}`;
    })
    .join("\n");
}

function wireToolbar(): void {
  $("#play").addEventListener("click", togglePlay);
  $("#clear").addEventListener("click", () => {
    state.tracks.forEach((t) => t.steps.fill(false));
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
    const wav = toWav(renderProject(snapshot(), 2, ctx!.sampleRate));
    const url = URL.createObjectURL(new Blob([wav.buffer as ArrayBuffer], { type: "audio/wav" }));
    const a = document.createElement("a");
    a.href = url; a.download = "audx-studio.wav"; a.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
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

  document.addEventListener("keydown", (e) => {
    if (e.code === "Space" && !(e.target as HTMLElement).matches("input,select,textarea")) {
      e.preventDefault();
      togglePlay();
    }
  });
}

function syncTransportInputs(): void {
  const bpm = $<HTMLInputElement>("#bpm");
  const swing = $<HTMLInputElement>("#swing");
  bpm.value = String(state.bpm);
  $("#bpm-val").textContent = String(state.bpm);
  swing.value = String(Math.round(state.swing * 100));
  $("#swing-val").textContent = `${Math.round(state.swing * 100)}%`;
}

loadSaved();
renderGrid();
wireToolbar();
syncTransportInputs();
paintTransport();
