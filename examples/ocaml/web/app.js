// The playground's whole browser side. Pyodide runs CPython in WebAssembly;
// the compiler and astero are pure Python with no dependencies, so the
// toolchain is one zip and one `unpackArchive` call.
//
// Bump this when the CDN drops a version. Nothing else here names one.
const PYODIDE_VERSION = "314.0.6";
const PYODIDE_URL = `https://cdn.jsdelivr.net/npm/pyodide@${PYODIDE_VERSION}/`;
const HOME = "/home/pyodide";
// The text panes, and the tabs. `names` is drawn from rows and `step` is a
// panel of controls, so neither is a block of text `render` fills in.
const TEXT_VIEWS = ["run", "types", "python", "printed"];
const VIEWS = [...TEXT_VIEWS, "names", "step"];
// What the page opens on when no link says otherwise: short, and in English
// and French alike.
const FIRST = "fact.ml";

// Every string the reader sees. `index.html` carries this edition's,
// which is how the page is French on /fr/ and English on /en/.
const S = window.STRINGS;

// The words for what the compiler reports by name.
const KINDS = {
  binding: S.kind_binding,
  let: S.kind_let,
  case: S.kind_case,
  fun: S.kind_fun,
  for: S.kind_for,
};
const NAMESPACES = {
  vals: S.ns_vals,
  cons: S.ns_cons,
  fields: S.ns_fields,
  types: S.ns_types,
  tyvars: S.ns_tyvars,
};
const GROUPS = {
  groupExamples: S.groupExamples,
  groupSimonet: S.groupSimonet,
  groupGrimaud: S.groupGrimaud,
};

const $ = (id) => document.getElementById(id);
const els = {
  source: $("source"),
  example: $("example"),
  run: $("run-button"),
  share: $("share"),
  status: $("status"),
  errors: $("errors"),
  stepAt: $("step-at"),
  stepCount: $("step-count"),
  stepNote: $("step-note"),
  stepSource: $("step-source"),
  stepWhere: $("step-where"),
  stepEnv: $("step-env"),
  stepStore: $("step-store"),
  stepPython: $("step-python"),
  stepOutput: $("step-output"),
  stepCursor: $("step-cursor"),
};

let analyse = null;
let stepping = null;
// The source the views were last computed from, and the corpus text of the
// programme picked in the list: an edit is anything that differs from them.
let lastRun = null;
let picked = null;

function say(text, tone = "") {
  els.status.textContent = text;
  els.status.className = tone;
}

// ------------------------------------------------------------------ sharing
//
// A link carries the programme after the `#`, which the browser never sends
// to a server: `#example=fact` for a corpus programme as it stands, and
// `#z=...` for anything else, deflated and then base64url-encoded, which is
// about a third of the length of the source. `#code=` is the older form,
// base64 without compression, still read so links already shared still open.

const toBase64 = (bytes) => {
  let binary = "";
  for (const byte of bytes) binary += String.fromCharCode(byte);
  return btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
};

const fromBase64 = (text) => {
  const padded = text.replace(/-/g, "+").replace(/_/g, "/");
  const binary = atob(padded + "=".repeat((4 - (padded.length % 4)) % 4));
  return Uint8Array.from(binary, (c) => c.charCodeAt(0));
};

const through = async (bytes, stream) =>
  new Uint8Array(await new Response(new Blob([bytes]).stream().pipeThrough(stream)).arrayBuffer());

async function pack(text) {
  const bytes = new TextEncoder().encode(text);
  return toBase64(await through(bytes, new CompressionStream("deflate-raw")));
}

async function unpack(text) {
  const bytes = await through(fromBase64(text), new DecompressionStream("deflate-raw"));
  return new TextDecoder().decode(bytes);
}

// What the fragment asks for: `{ example }`, `{ source }`, or null.
async function fromFragment() {
  const found = /(?:^|[#&])(example|z|code)=([^&]+)/.exec(location.hash);
  if (!found) return null;
  const [, kind, value] = found;
  try {
    if (kind === "example") return { example: decodeURIComponent(value) };
    if (kind === "z") return { source: await unpack(value) };
    return { source: new TextDecoder().decode(fromBase64(value)) };
  } catch {
    return null;
  }
}

// The address bar says what is on the page, or nothing: a link left over
// from another programme would reload the wrong one.
function setFragment(fragment) {
  history.replaceState(null, "", `${location.pathname}${fragment ? `#${fragment}` : ""}`);
}

// -------------------------------------------------------------------- views

function show(name) {
  for (const view of VIEWS) $(view).hidden = view !== name;
  for (const hint of document.querySelectorAll("[data-hint]")) {
    hint.hidden = hint.dataset.hint !== name;
  }
  for (const tab of document.querySelectorAll('[role="tab"]')) {
    tab.setAttribute("aria-selected", String(tab.dataset.view === name));
  }
  // Recording costs more than running, so it waits until someone asks.
  if (name === "step" && trace === null) record();
}

function render(found) {
  // A new run invalidates the recording; the Step view records again when
  // it is next opened.
  trace = null;
  for (const view of TEXT_VIEWS) $(view).textContent = found[view] || "";
  drawScopes(found);
  const problems = found.errors || [];
  els.errors.hidden = problems.length === 0;
  els.errors.textContent = problems.join("\n");
  if (problems.length) show("run");
}


// The Names view, from the rows `pipeline.scope_rows` gives: one per part of
// the programme that opens a scope, labelled in words, with the line it
// starts on. Clicking a row selects that line in the source.
function drawScopes(found) {
  const view = $("names");
  view.textContent = "";
  if (found.unbound && found.unbound.length) {
    const warn = document.createElement("pre");
    warn.className = "unbound";
    warn.textContent = found.unbound.join("\n");
    view.append(warn);
  }
  for (const { ns, rows } of found.scopes || []) {
    const section = document.createElement("section");
    const heading = document.createElement("h3");
    heading.textContent = NAMESPACES[ns] || ns;
    section.append(heading);
    for (const [depth, kind, name, line, names] of rows) {
      section.append(scopeRow(depth, kind, name, line, names));
    }
    view.append(section);
  }
}

function scopeRow(depth, kind, name, line, names) {
  const row = document.createElement("div");
  row.className = "scope-row";
  row.style.paddingLeft = `${0.3 + depth * 1.4}rem`;
  const what = document.createElement("span");
  what.className = "what";
  what.append(depth === 0 ? S.kind_module : KINDS[kind] || kind);
  if (name) {
    const code = document.createElement("code");
    code.textContent = name;
    what.append(" ", code);
  }
  if (depth > 0 && line) {
    const where = document.createElement("span");
    where.className = "where";
    where.textContent = ` \u00b7 ${S.line} ${line}`;
    what.append(where);
    row.addEventListener("click", () => selectLine(line));
  }
  const bound = document.createElement("span");
  bound.className = names.length ? "names" : "names none";
  bound.textContent = names.length ? names.join(", ") : "\u2014";
  row.append(what, bound);
  return row;
}

function selectLine(line) {
  const text = els.source.value;
  let from = 0;
  for (let n = 1; n < line; n += 1) from = text.indexOf("\n", from) + 1;
  const to = text.indexOf("\n", from);
  els.source.focus();
  els.source.setSelectionRange(from, to < 0 ? text.length : to);
  const height = parseFloat(getComputedStyle(els.source).lineHeight) || 20;
  els.source.scrollTop = Math.max(0, (line - 3) * height);
}

// ------------------------------------------------------------------ stepping
//
// The whole run is recorded before the first step is shown, which is what
// makes going backwards free: it is an index into a list, not a second run.
// `at` is where we are in that list, and every button computes a new `at`.

let trace = null;
let at = 0;

const escaped = (text) =>
  text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");

function record() {
  if (!stepping) return;
  say(S.recording);
  const proxy = stepping(els.source.value);
  try {
    trace = proxy.toJs({ dict_converter: Object.fromEntries });
  } finally {
    proxy.destroy();
  }
  at = 0;
  els.stepAt.max = String(Math.max(0, trace.steps.length - 1));
  const notes = [];
  if (trace.truncated) notes.push(`${S.truncated} ${trace.steps.length}`);
  if (trace.error) notes.push(trace.error);
  if (trace.errors && trace.errors.length) notes.push(trace.errors.join("\n"));
  els.stepNote.hidden = notes.length === 0;
  els.stepNote.textContent = notes.join(" · ");
  draw();
  say(`${trace.steps.length} ${S.steps}`);
}

// The emitted Python takes its own steps and there is no honest mapping
// between them, so the two are lined up on the one thing they share: how
// much each has printed. Exact where output happens, nearest-so-far between.
function pyStepFor(printed) {
  const steps = trace.pysteps || [];
  let found = null;
  for (const step of steps) {
    if (step.printed <= printed) found = step;
    else break;
  }
  return found;
}

function rows(table, pairs, empty) {
  table.textContent = "";
  if (!pairs.length) {
    const row = table.insertRow();
    const cell = row.insertCell();
    cell.colSpan = 2;
    cell.className = "quiet";
    cell.textContent = empty;
    return;
  }
  for (const [name, value] of pairs) {
    const row = table.insertRow();
    row.insertCell().textContent = name;
    row.insertCell().textContent = value;
  }
}

function draw() {
  if (!trace || !trace.steps.length) {
    els.stepSource.textContent = "";
    els.stepCount.textContent = "0 / 0";
    return;
  }
  const step = trace.steps[at];
  const source = els.source.value;
  els.stepAt.value = String(at);
  els.stepCount.textContent = `${at + 1} / ${trace.steps.length}`;

  let shown = "";
  if (step.span) {
    const [from, to] = step.span;
    shown = source.slice(from, to);
    els.stepSource.innerHTML =
      escaped(source.slice(0, from)) +
      `<mark class="${step.kind}">${escaped(shown)}</mark>` +
      escaped(source.slice(to));
    // Keep the marked expression in sight: without this it scrolled out of
    // the box after a few steps and the view seemed to do nothing.
    const mark = els.stepSource.querySelector("mark");
    els.stepSource.scrollTop = Math.max(0, mark.offsetTop - els.stepSource.clientHeight / 3);
  } else {
    els.stepSource.textContent = source;
  }

  // Pyodide turns Python's `None` into `undefined`, not `null`.
  const done = step.kind !== "enter" && step.value != null;
  const brief = shown.replace(/\s+/g, " ").trim();
  const said = brief.length > 60 ? `${brief.slice(0, 57)}\u2026` : brief;
  els.stepWhere.textContent = "";
  whereLine(done ? S.gives : S.evaluating, said, done ? step.value : null);
  whereLine(S.calls, step.stack.join(" \u25b8 "));
  whereLine(S.scope, inWords(step.scope));

  rows(els.stepEnv, step.env, S.nothingBound);
  rows(els.stepStore, step.store, S.nothingMutable);

  const py = pyStepFor(step.printed);
  els.stepPython.textContent = py ? `${py.line}  ${py.text}` : S.notYet;
  els.stepOutput.textContent = trace.output.slice(0, step.printed);
}

// The scope path the stepper reports, `top ▸ binding ▸ case`, in the words
// the Names view uses for the same blocks.
function inWords(path) {
  return path
    .split(" \u25b8 ")
    .map((part) => (part === "top" ? S.kind_module : KINDS[part] || part))
    .join(" \u25b8 ");
}

function whereLine(label, code, value = null) {
  const line = document.createElement("div");
  const name = document.createElement("span");
  name.className = "label";
  name.textContent = label;
  const text = document.createElement("code");
  text.textContent = value === null ? code : `${code}  \u21d2  ${value}`;
  line.append(name, text);
  els.stepWhere.append(line);
}

// Step over, in and out count function calls rather than sub-expressions:
// every operand of an expression is deeper and none of them is a call.
function moveTo(next) {
  at = Math.max(0, Math.min(trace.steps.length - 1, next));
  draw();
}

function seek(direction, test) {
  const here = trace.steps[at].call;
  for (let i = at + direction; i >= 0 && i < trace.steps.length; i += direction) {
    if (test(trace.steps[i].call, here)) return moveTo(i);
  }
  moveTo(direction > 0 ? trace.steps.length - 1 : 0);
}

const MOVES = {
  start: () => moveTo(0),
  end: () => moveTo(trace.steps.length - 1),
  back: () => moveTo(at - 1),
  forward: () => moveTo(at + 1),
  in: () => seek(1, (call, here) => call > here),
  out: () => seek(1, (call, here) => call < here),
};

function toCursor() {
  const where = els.source.selectionStart;
  const found = trace.steps.findIndex(
    (step) => step.span && step.span[0] <= where && where < step.span[1],
  );
  if (found >= 0) moveTo(found);
}

function wireStepping() {
  for (const button of document.querySelectorAll("[data-step]")) {
    button.addEventListener("click", () => {
      if (trace && trace.steps.length) MOVES[button.dataset.step]();
    });
  }
  els.stepAt.addEventListener("input", () => {
    if (trace) moveTo(Number(els.stepAt.value));
  });
  els.stepCursor.addEventListener("click", () => {
    if (trace && trace.steps.length) toCursor();
  });
  document.addEventListener("keydown", (event) => {
    if ($("step").hidden || !trace || event.metaKey || event.ctrlKey) return;
    if (event.target === els.source) return;
    const move = { ArrowRight: "forward", ArrowLeft: "back" }[event.key];
    if (move) {
      event.preventDefault();
      MOVES[move]();
    }
  });
}

// --------------------------------------------------------------------- work

function run() {
  if (!analyse) return;
  lastRun = els.source.value;
  edited();
  const started = performance.now();
  say(S.running);
  let found;
  const proxy = analyse(els.source.value);
  try {
    found = proxy.toJs({ dict_converter: Object.fromEntries });
  } finally {
    proxy.destroy();
  }
  render(found);
  const took = Math.round(performance.now() - started);
  if (found.errors.length) {
    say(`${found.errors.length} ${S.problems} · ${took} ms`, "bad");
  } else if (!found.ran) {
    say(`${took} ms`);
  } else if (found.agree) {
    say(`${S.agree} · ${took} ms`, "good");
  } else {
    say(`${S.disagree} · ${took} ms`, "bad");
  }
}

// --------------------------------------------------------------------- boot

// After an edit the views describe the old source, so they dim and Run is
// the one thing to press; with nothing new to run, Run is off.
function edited() {
  const changed = els.source.value !== lastRun;
  els.run.disabled = !changed;
  $("views").classList.toggle("stale", changed);
  if (changed) say(S.edited);
  if (picked !== null && els.source.value !== picked) {
    picked = null;
    els.example.value = "";
    setFragment("");
  }
}

function loadScript(url) {
  return new Promise((done, failed) => {
    const tag = document.createElement("script");
    tag.src = url;
    tag.onload = done;
    tag.onerror = () => failed(new Error(`cannot load ${url}`));
    document.head.append(tag);
  });
}

async function boot() {
  say(S.loadingPython);
  await loadScript(`${PYODIDE_URL}pyodide.js`);
  const py = await loadPyodide({ indexURL: PYODIDE_URL });

  say(S.loadingCompiler);
  const bundle = await fetch("py/playground.zip");
  if (!bundle.ok) {
    throw new Error(S.noBundle);
  }
  await py.unpackArchive(await bundle.arrayBuffer(), "zip", { extractDir: HOME });
  py.runPython(`import sys\nsys.path.insert(0, ${JSON.stringify(HOME)})`);
  analyse = py.runPython("from ocaml.pipeline import analyse\nanalyse");
  stepping = py.runPython("from ocaml.pipeline import stepping\nstepping");
  wireStepping();

  // Grouped by the set each programme comes from, as `build.py` wrote it.
  const groups = JSON.parse(
    py.FS.readFile(`${HOME}/corpus/groups.json`, { encoding: "utf8" }),
  );
  // Selected while the source is not a corpus programme as it stands.
  const mine = document.createElement("option");
  mine.value = "";
  mine.disabled = true;
  mine.hidden = true;
  mine.textContent = S.mine;
  els.example.append(mine);
  for (const [label, names] of Object.entries(groups)) {
    const group = document.createElement("optgroup");
    group.label = GROUPS[label] || label;
    for (const name of names) {
      const option = document.createElement("option");
      option.value = name;
      option.textContent = name.replace(/\.ml$/, "");
      group.append(option);
    }
    els.example.append(group);
  }

  const load = (name) =>
    py.FS.readFile(`${HOME}/corpus/${name}`, { encoding: "utf8" });

  const known = new Set(Object.values(groups).flat());
  const pick = (name) => {
    picked = load(name);
    els.source.value = picked;
    els.example.value = name;
    setFragment(`example=${name.replace(/\.ml$/, "")}`);
  };

  els.example.addEventListener("change", () => {
    pick(els.example.value);
    run();
  });

  const wanted = await fromFragment();
  const named = wanted && wanted.example ? `${wanted.example}.ml` : null;
  if (named && known.has(named)) {
    pick(named);
  } else if (wanted && wanted.source !== undefined) {
    els.source.value = wanted.source;
    els.example.value = "";
  } else {
    pick(FIRST);
  }

  els.example.disabled = false;
  els.share.disabled = false;
  els.source.addEventListener("input", edited);
  run();
}

// ------------------------------------------------------------------- wiring

for (const tab of document.querySelectorAll('[role="tab"]')) {
  tab.addEventListener("click", () => show(tab.dataset.view));
}

els.run.addEventListener("click", run);

// Switching language from here is a plain link; this only records the
// choice, under the key the chooser at the site root reads.
for (const link of document.querySelectorAll("a.switch[data-lang]")) {
  link.addEventListener("click", () => {
    try {
      localStorage.setItem("caml-prepa:lang", link.dataset.lang);
    } catch {
      /* a browser that refuses storage still follows the link */
    }
  });
}

els.source.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && (event.metaKey || event.ctrlKey)) {
    event.preventDefault();
    run();
  }
});

els.share.addEventListener("click", async () => {
  const name = els.example.value;
  const fragment =
    picked !== null && name
      ? `example=${name.replace(/\.ml$/, "")}`
      : `z=${await pack(els.source.value)}`;
  setFragment(fragment);
  const url = location.href;
  try {
    await navigator.clipboard.writeText(url);
    say(S.linkCopied);
  } catch {
    say(S.linkInBar);
  }
});

boot().catch((bad) => {
  say(String(bad.message || bad), "bad");
  els.errors.hidden = false;
  els.errors.textContent = `${bad}\n\n${S.bootHelp}`;
});
