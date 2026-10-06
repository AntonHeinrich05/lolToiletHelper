/* Shared source: copied into Chromium/Firefox release folders by package.py.
   No content scripts, injected keys, browsing-history upload or remote server. */
/* global chrome, browser */
"use strict";
const api = typeof browser !== "undefined" ? browser : chrome;
const HOST = "de.lolautopicker.bridge";
let port = null;
let connected = false;
let connecting = false;
let context = {live_tracking: false, champion: ""};
let managed = {};
let waiting = new Map();
let commandTail = Promise.resolve();
let eventTail = Promise.resolve();
let reconnectTimer;
let retryDelay = 500;

function canonical(raw) {
  if (typeof raw !== "string" || raw.length > 8192) throw new Error("Ungültige URL");
  const u = new URL(raw);
  if (!["https:", "http:"].includes(u.protocol) || !["lolalytics.com", "www.lolalytics.com"].includes(u.hostname)
      || u.username || u.password || (u.port && !["80", "443"].includes(u.port))) throw new Error("Nur Lolalytics erlaubt");
  u.protocol = "https:"; u.hostname = "lolalytics.com"; u.port = "";
  u.pathname = u.pathname.replace(/\/+$/, "") + "/";
  if (!/^\/lol\/[a-z0-9]+\/(?:[a-z0-9]+\/)*$/.test(u.pathname)) throw new Error("Keine Champion-Seite");
  u.searchParams.sort();
  return u.href;
}
function identity(url) {
  const p = new URL(canonical(url)).pathname.split("/").filter(Boolean);
  return {champion: p[1], opponent: p[2] === "vs" ? p[3] : "",
    mode: p.includes("aram") ? "aram" : p.includes("arena") ? "arena" : "classic"};
}
function matches(url, champion) {
  try { return identity(url).champion === champion; } catch { return false; }
}
function send(message) {
  if (!port || !connected) throw new Error("Autopicker ist nicht verbunden");
  port.postMessage(message);
}
function request(message) {
  return new Promise((resolve, reject) => {
    const id = crypto.randomUUID();
    const timer = setTimeout(() => {waiting.delete(id); reject(new Error("Speichern nicht bestätigt; Tab bleibt offen"));}, 7000);
    waiting.set(id, {resolve, reject, timer});
    try { send({...message, id}); } catch (e) {clearTimeout(timer); waiting.delete(id); reject(e);}
  });
}
async function badge(text, title) {
  const action = api.action || api.browserAction;
  await action.setBadgeText({text});
  await action.setTitle({title});
}
async function persist() { await api.storage.session.set({managed}); }
async function persistError(error) {
  await api.storage.local.set({lastError: String(error.message || error)});
  await badge("!", String(error.message || error));
}
async function save(tab, meta) {
  const url = tab.url || tab.pendingUrl;
  if (!meta || !matches(url, meta.champion)) return;
  await request({event: "save", url: canonical(url), champion: meta.champion, kind: meta.kind});
}
async function focus(tab) {
  await api.tabs.update(tab.id, {active: true});
  await api.windows.update(tab.windowId, {focused: true});
}
async function openManaged(cmd) {
  const url = canonical(cmd.url);
  const tabs = await api.tabs.query({});
  const existing = tabs.find(t => {
    try {return canonical(t.pendingUrl || t.url) === url;} catch {return false;}
  });
  const tab = existing || await api.tabs.create({url, active: true});
  const meta = {champion: identity(url).champion, kind: cmd.kind === "vs" ? "vs" : "base", lastUrl: url};
  managed[tab.id] = meta;
  await persist();
  await save({...tab, url}, meta);
  await focus(tab); // hotkey from inside the game: bring the browser window to the front as well
  return {reused: !!existing, tab_id: tab.id, url};
}
function isLolalytics(url) {
  try { return ["lolalytics.com", "www.lolalytics.com"].includes(new URL(url).hostname); } catch { return false; }
}
async function closeLolalytics() {
  // Every Lolalytics tab (also after navigating to another champion), never other sites.
  const tabs = await api.tabs.query({});
  const targets = tabs.filter(t => isLolalytics(t.url || t.pendingUrl));
  let failed = 0;
  for (const tab of targets) {
    const meta = managed[tab.id] || (context.champion ? {champion: context.champion, kind: "base"} : null);
    // Save the last URL before closing, but a failed save must not keep the tab open.
    try { await save(tab, meta); } catch (error) { failed++; console.info("Speichern vor dem Schließen fehlgeschlagen:", error.message); }
    await api.tabs.remove(tab.id);
    delete managed[tab.id];
  }
  await persist();
  return {closed: targets.length, save_failed: failed};
}
async function closeWindows() {
  // "Ganze Browser" scope: save Lolalytics URLs, then close every window of this browser (the user chose this explicitly).
  const tabs = await api.tabs.query({});
  for (const tab of tabs.filter(t => isLolalytics(t.url || t.pendingUrl))) {
    const meta = managed[tab.id] || (context.champion ? {champion: context.champion, kind: "base"} : null);
    try { await save(tab, meta); } catch (error) { console.info("Speichern vor dem Schließen fehlgeschlagen:", error.message); }
  }
  managed = {};
  await persist();
  const windows = await api.windows.getAll();
  for (const win of windows) await api.windows.remove(win.id);
  return {closed: tabs.length, windows: windows.length};
}
async function snapshotManaged() {
  const tabs = await api.tabs.query({});
  for (const tab of tabs) {
    const meta = managed[tab.id];
    if (meta) await save(tab, meta);
    else if (context.champion && matches(tab.url, context.champion)) {
      await save(tab, {champion: context.champion, kind: "base"});
    }
  }
  return {saved: true};
}
async function correctVs(cmd) {
  const fresh = new URL(canonical(cmd.url));
  const tabs = await api.tabs.query({});
  let updated = 0;
  for (const tab of tabs) {
    const meta = managed[tab.id];
    if (!meta || meta.kind !== "vs" || !matches(tab.url, cmd.champion)) continue;
    const old = new URL(canonical(tab.url));
    const target = new URL(fresh);
    target.search = old.search;
    target.searchParams.delete("lane"); target.searchParams.delete("vslane");
    for (const [k, v] of fresh.searchParams) {
      if (["lane", "vslane"].includes(k) || !target.searchParams.has(k)) target.searchParams.set(k, v);
    }
    const url = canonical(target.href);
    if (canonical(old.href) === url) continue;
    await save({url}, meta);
    meta.lastUrl = url;
    const duplicate = tabs.find(other => {
      try {return other.id !== tab.id && canonical(other.url) === url;} catch {return false;}
    });
    if (duplicate) {
      managed[duplicate.id] = {...meta, lastUrl: url};
      await api.tabs.remove(tab.id);
      delete managed[tab.id];
    } else {
      await api.tabs.update(tab.id, {url}); // no foreground/focus steal
      managed[tab.id].lastUrl = url;
    }
    updated++;
  }
  await persist();
  return {updated};
}
async function command(cmd) {
  switch (cmd.command) {
    case "open": return openManaged(cmd);
    case "close": return closeLolalytics();
    case "close_all": return closeLolalytics();
    case "close_lolalytics": return closeLolalytics();
    case "close_windows": return closeWindows();
    case "snapshot": return snapshotManaged();
    case "correct_vs": return correctVs(cmd);
    default: throw new Error("Unbekannte Aktion");
  }
}
function onMessage(message) {
  if (message.event === "bridge_status" && !message.connected) {
    connected = false;
    for (const item of waiting.values()) {
      clearTimeout(item.timer);
      item.reject(new Error("Autopicker verbindet sich gerade"));
    }
    waiting.clear();
    badge("…", "Browser-Brücke bereit — wartet auf Autopicker").catch(() => {});
    return;
  }
  if (message.reply_to && waiting.has(message.reply_to)) {
    const item = waiting.get(message.reply_to);
    clearTimeout(item.timer); waiting.delete(message.reply_to);
    if (message.ok) item.resolve(message); else item.reject(new Error(message.error || "Speichern fehlgeschlagen"));
    return;
  }
  if (message.event === "context") {
    const initial = !connected;
    connected = true; retryDelay = 500;
    context = {live_tracking: !!message.live_tracking, champion: message.champion || ""};
    badge("ON", "Autopicker verbunden — klicken, um diesen Browser auszuwählen").catch(() => {});
    if (initial || context.live_tracking) enqueueEvent(async () => {
      const tabs = await api.tabs.query({});
      for (const tab of tabs) await track(tab.id, tab.url || tab.pendingUrl);
    });
    return;
  }
  if (message.id && message.command) {
    if (!connected) return; // the native host relays commands only after the context handshake
    // Serialize ALL mutations: spam cannot pass multiple simultaneous query/create checks.
    commandTail = commandTail.catch(() => {}).then(async () => {
      try {const result = await command(message); send({reply_to: message.id, ok: true, ...result});}
      catch (error) {
        try {send({reply_to: message.id, ok: false, error: error.message});} catch { /* disconnected */ }
        await persistError(error);
      }
    });
  }
}
function browserName() {
  if (typeof browser !== "undefined") return "Firefox";
  if (navigator.userAgent.includes("Edg/")) return "Microsoft Edge";
  if (navigator.userAgent.includes("OPR/")) return "Opera";
  return "Chromium-Browser";
}
async function connect() {
  if (port || connecting) return;
  connecting = true;
  clearTimeout(reconnectTimer);
  try {
    const saved = await api.storage.local.get(["clientId"]);
    const session = await api.storage.session.get(["managed"]);
    managed = session.managed || {};
    const tabs = await api.tabs.query({});
    const alive = new Set(tabs.filter(t => managed[t.id] && matches(t.url || t.pendingUrl, managed[t.id].champion)).map(t => String(t.id)));
    for (const id of Object.keys(managed)) if (!alive.has(id)) delete managed[id];
    await persist();
    const clientId = saved.clientId || crypto.randomUUID();
    await api.storage.local.set({clientId});
    const current = api.runtime.connectNative(HOST);
    port = current;
    current.onMessage.addListener(onMessage);
    current.onDisconnect.addListener(() => {
      const detail = api.runtime.lastError;
      if (detail) console.info("Native Host:", detail.message);
      if (port !== current) return;
      port = null; connected = false;
      for (const item of waiting.values()) {clearTimeout(item.timer); item.reject(new Error("Verbindung beendet"));}
      waiting.clear();
      badge("OFF", "Autopicker starten / Browser-Bridge installieren; dann hier klicken").catch(() => {});
      reconnectTimer = setTimeout(() => connect().catch(persistError), retryDelay);
      retryDelay = Math.min(retryDelay * 2, 2000);
    });
    current.postMessage({event: "hello", client_id: clientId, name: browserName() + " · " + clientId.slice(0, 4)});
  } catch (error) {port = null; await persistError(error);}
  finally {connecting = false;}
}
async function track(tabId, url) {
  const meta = managed[tabId];
  if (meta && matches(url, meta.champion)) {
    meta.lastUrl = canonical(url);
    await persist();
    if (connected && context.live_tracking) await save({url}, meta);
  } else if (connected && context.live_tracking && context.champion && matches(url, context.champion)) {
    // Track matching manually opened pages, but NEVER claim ownership/close them.
    await save({url}, {champion: context.champion, kind: "base"});
  }
}
function enqueueEvent(action) {
  eventTail = eventTail.catch(() => {}).then(action).catch(persistError);
}
api.tabs.onUpdated.addListener((id, changes, tab) => {
  if (changes.url) enqueueEvent(() => track(id, changes.url));
  else if (changes.status === "complete") enqueueEvent(() => track(id, tab.url));
});
api.webNavigation.onHistoryStateUpdated.addListener(details => {
  if (details.frameId === 0) enqueueEvent(() => track(details.tabId, details.url));
}, {url: [{hostEquals: "lolalytics.com"}, {hostEquals: "www.lolalytics.com"}]});
api.webNavigation.onReferenceFragmentUpdated.addListener(details => {
  if (details.frameId === 0) enqueueEvent(() => track(details.tabId, details.url));
}, {url: [{hostEquals: "lolalytics.com"}, {hostEquals: "www.lolalytics.com"}]});
api.tabs.onRemoved.addListener(id => enqueueEvent(async () => {
  const meta = managed[id];
  // Native Ctrl+W: only the last observed URL is available after removal.
  if (connected && meta?.lastUrl) await save({url: meta.lastUrl}, meta);
  delete managed[id]; await persist();
}));
(api.action || api.browserAction).onClicked.addListener(() => {
  if (!connected) connect().catch(persistError);
  else request({event: "select_browser"}).then(() => badge("OK", "Dieser Browser ist ausgewählt")).catch(persistError);
});
api.runtime.onStartup.addListener(() => connect().catch(persistError));
api.runtime.onInstalled.addListener(() => connect().catch(persistError));
api.alarms.onAlarm.addListener(alarm => {if (alarm.name === "reconnect" && !port) connect().catch(persistError);});
api.alarms.create("reconnect", {periodInMinutes: 1});
connect().catch(persistError);