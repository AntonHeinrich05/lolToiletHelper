// Regression harness for production extension/shared/background.js via Node VM.
const assert = require('node:assert/strict');
const {test} = require('node:test');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');

function eventBus() {
  const listeners = [];
  return {
    addListener(fn) { listeners.push(fn); },
    trigger(...args) { for (const fn of listeners) fn(...args); },
  };
}

function createHarness(options = {}) {
  const sharedLocal = options.localStore || {};
  const sharedSession = options.sessionStore || {};
  let ackMode = options.ackMode || 'ok';
  let now = 1;
  const events = [];
  const tabs = (options.initialTabs || []).map(t => ({...t}));
  let nextId = tabs.length ? Math.max(...tabs.map(t => t.id)) + 1 : 1;
  const onMessage = eventBus();
  const onDisconnect = eventBus();
  let connectCalls = 0;

  const port = {
    posted: [],
    onMessage,
    onDisconnect,
    postMessage(msg) {
      this.posted.push(msg);
      if (msg.event === 'save') {
        events.push(`save:${msg.id}`);
        if (ackMode === 'ok') setImmediate(() => onMessage.trigger({reply_to: msg.id, ok: true}));
        if (ackMode === 'fail') setImmediate(() => onMessage.trigger({reply_to: msg.id, ok: false, error: 'save failed'}));
      }
    },
  };

  const api = {
    tabs: {
      _updates: [],
      _removes: [],
      _creates: 0,
      async query() { return tabs.map(t => ({...t})); },
      async create({url, active}) {
        const tab = {id: nextId++, url, pendingUrl: undefined, active: !!active, windowId: 1, lastAccessed: ++now};
        tabs.push(tab);
        this._creates++;
        return {...tab};
      },
      async update(id, patch) {
        const tab = tabs.find(t => t.id === id);
        Object.assign(tab, patch);
        if (patch.active !== undefined) tab.active = patch.active;
        tab.lastAccessed = ++now;
        this._updates.push({id, patch: {...patch}});
        return {...tab};
      },
      async remove(id) {
        const idx = tabs.findIndex(t => t.id === id);
        if (idx >= 0) tabs.splice(idx, 1);
        this._removes.push(id);
        events.push(`remove:${id}`);
      },
      onUpdated: eventBus(),
      onRemoved: eventBus(),
    },
    windows: {
      _updates: [],
      _removes: [],
      async update(id, patch) { this._updates.push({id, patch}); },
      async getAll() { return [...new Set(tabs.map(t => t.windowId || 1))].map(id => ({id})); },
      async remove(id) {
        this._removes.push(id);
        for (let i = tabs.length - 1; i >= 0; i--) if ((tabs[i].windowId || 1) === id) tabs.splice(i, 1);
      },
    },
    storage: {
      local: {
        async get(keys) {
          const result = {};
          for (const key of keys) result[key] = sharedLocal[key];
          return result;
        },
        async set(obj) { Object.assign(sharedLocal, obj); },
      },
      session: {
        async get(keys) {
          const result = {};
          for (const key of keys) result[key] = sharedSession[key];
          return result;
        },
        async set(obj) { Object.assign(sharedSession, obj); },
      },
    },
    runtime: {
      lastError: null,
      connectNative() { connectCalls++; return port; },
      onStartup: eventBus(),
      onInstalled: eventBus(),
    },
    action: {
      async setBadgeText() {},
      async setTitle() {},
      onClicked: eventBus(),
    },
    webNavigation: {
      onHistoryStateUpdated: eventBus(),
      onReferenceFragmentUpdated: eventBus(),
    },
    alarms: {
      onAlarm: eventBus(),
      create() {},
    },
  };

  const sandbox = {
    chrome: api,
    browser: undefined,
    navigator: {userAgent: 'Chrome'},
    crypto: {randomUUID: (() => { let i = 0; return () => `id-${++i}`; })()},
    URL,
    setTimeout,
    clearTimeout,
    setImmediate,
    Promise,
    console,
  };

  const source = fs.readFileSync(path.resolve(__dirname, '../extension/shared/background.js'), 'utf8');
  vm.runInNewContext(source, sandbox, {filename: 'background.js'});

  return {
    api,
    port,
    tabs,
    events,
    sharedLocal,
    sharedSession,
    connectCalls: () => connectCalls,
    setAckMode(mode) { ackMode = mode; },
    fromApp(message) { onMessage.trigger(message); },
    async tick(ms = 25) { await new Promise(resolve => setTimeout(resolve, ms)); },
  };
}

test('20 simultaneous open commands dedupe to one tab', async () => {
  const h = createHarness();
  await h.tick(40);
  h.fromApp({event: 'context', live_tracking: true, champion: 'aatrox'});
  await h.tick(20);
  for (let i = 0; i < 20; i++) {
    h.fromApp({id: `open-${i}`, command: 'open', kind: 'base', url: 'https://lolalytics.com/lol/aatrox/build/?tier=all'});
  }
  await h.tick(300);
  assert.equal(h.api.tabs._creates, 1);
  assert.equal(h.tabs.length, 1);
  assert.equal(h.port.posted.filter(m => m.reply_to && m.reply_to.startsWith('open-')).length, 20);
});

test('distinct URL parameters create distinct tabs', async () => {
  const h = createHarness();
  await h.tick(40);
  h.fromApp({event: 'context', live_tracking: true, champion: 'aatrox'});
  await h.tick(20);
  h.fromApp({id: 'a', command: 'open', kind: 'base', url: 'https://lolalytics.com/lol/aatrox/build/?tier=all&item=1_6692'});
  h.fromApp({id: 'b', command: 'open', kind: 'base', url: 'https://lolalytics.com/lol/aatrox/build/?tier=all&item=1_3071'});
  await h.tick(200);
  assert.equal(h.tabs.length, 2);
});

test('close saves first, then closes EVERY lolalytics tab (also after navigating to another champion), never other sites', async () => {
  const h = createHarness({initialTabs: [{id: 50, url: 'https://www.google.com/', active: false, windowId: 1}]});
  await h.tick(40);
  h.fromApp({event: 'context', live_tracking: false, champion: 'aatrox'});
  await h.tick(20);
  h.fromApp({id: 'open', command: 'open', kind: 'base', url: 'https://lolalytics.com/lol/aatrox/build/?tier=all'});
  await h.tick(120);
  assert.ok(h.api.windows._updates.some(u => u.patch.focused), 'new tab must bring its window to the front');
  // user navigated inside Lolalytics to another champion + a manually opened Lolalytics tab
  const managedTab = h.tabs.find(t => t.url.includes('aatrox'));
  managedTab.url = 'https://lolalytics.com/lol/jinx/build/?tier=all';
  h.tabs.push({id: 60, url: 'https://lolalytics.com/lol/ahri/aram/build/', active: false, windowId: 1});

  h.fromApp({id: 'close-ok', command: 'close'});
  await h.tick(150);
  const reply = h.port.posted.find(m => m.reply_to === 'close-ok');
  assert.equal(reply.ok, true);
  assert.equal(reply.closed, 2);
  assert.deepEqual(h.tabs.map(t => t.id), [50], 'only the google tab survives');

  h.fromApp({id: 'open2', command: 'open', kind: 'base', url: 'https://lolalytics.com/lol/aatrox/build/?tier=all'});
  await h.tick(120);
  const saveCount = h.events.length;
  h.setAckMode('fail');
  h.fromApp({id: 'close-fail', command: 'close_lolalytics'});
  await h.tick(150);
  const saveIndex = h.events.slice(saveCount).findIndex(e => e.startsWith('save:'));
  const removeIndex = h.events.slice(saveCount).findIndex(e => e.startsWith('remove:'));
  assert.ok(saveIndex >= 0 && removeIndex > saveIndex, 'save is attempted before remove');
  assert.deepEqual(h.tabs.map(t => t.id), [50], 'a failed save must not keep the Lolalytics tab open');
  const failReply = h.port.posted.find(m => m.reply_to === 'close-fail');
  assert.equal(failReply.ok, true);
  assert.equal(failReply.save_failed, 1);
});

test('close_windows saves Lolalytics URLs and closes every browser window (explicit "Ganze Browser" scope)', async () => {
  const h = createHarness({initialTabs: [{id: 50, url: 'https://www.google.com/', active: false, windowId: 2}]});
  await h.tick(40);
  h.fromApp({event: 'context', live_tracking: false, champion: 'aatrox'});
  await h.tick(20);
  h.fromApp({id: 'open', command: 'open', kind: 'base', url: 'https://lolalytics.com/lol/aatrox/build/?tier=all'});
  await h.tick(120);
  h.fromApp({id: 'cw', command: 'close_windows'});
  await h.tick(150);
  const reply = h.port.posted.find(m => m.reply_to === 'cw');
  assert.equal(reply.ok, true);
  assert.equal(reply.windows, 2);
  assert.ok(h.events.some(e => e.startsWith('save:')), 'Lolalytics URL saved before closing');
  assert.deepEqual(h.tabs, [], 'all windows (and thus all tabs) are gone');
  assert.equal(Object.keys(h.sharedSession.managed).length, 0);
});

test('correct_vs dedupes and does not steal focus', async () => {
  const h = createHarness();
  await h.tick(40);
  h.fromApp({event: 'context', live_tracking: true, champion: 'aatrox'});
  await h.tick(20);
  h.fromApp({id: 'v1', command: 'open', kind: 'vs', url: 'https://lolalytics.com/lol/aatrox/vs/caitlyn/build/?tier=all&item=1_6692&vslane=bottom'});
  h.fromApp({id: 'v2', command: 'open', kind: 'vs', url: 'https://lolalytics.com/lol/aatrox/vs/kennen/build/?tier=all&item=1_6692&vslane=middle'});
  await h.tick(200);
  const focusUpdates = h.api.windows._updates.length; // opening via hotkey focuses on purpose
  h.fromApp({id: 'fix', command: 'correct_vs', champion: 'aatrox', url: 'https://lolalytics.com/lol/aatrox/vs/kennen/build/?tier=all&vslane=middle'});
  await h.tick(200);
  assert.ok(h.api.tabs._removes.length >= 1);
  assert.equal(h.api.windows._updates.length, focusUpdates);
});

test('storage.session survives worker restart but not browser restart', async () => {
  const sessionStore = {};
  const localStore = {};

  const first = createHarness({sessionStore, localStore});
  await first.tick(40);
  first.fromApp({event: 'context', live_tracking: false, champion: 'aatrox'});
  await first.tick(20);
  first.fromApp({id: 'open', command: 'open', kind: 'base', url: 'https://lolalytics.com/lol/aatrox/build/?tier=all'});
  await first.tick(120);
  const initialTabs = first.tabs.map(t => ({...t}));
  assert.ok(sessionStore.managed && Object.keys(sessionStore.managed).length === 1);

  const restartedWorker = createHarness({sessionStore, localStore, initialTabs});
  await restartedWorker.tick(40);
  restartedWorker.fromApp({event: 'context', live_tracking: false, champion: 'aatrox'});
  await restartedWorker.tick(20);
  restartedWorker.fromApp({id: 'close', command: 'close'});
  await restartedWorker.tick(200);
  const closeReply = restartedWorker.port.posted.find(m => m.reply_to === 'close');
  assert.equal(closeReply.closed, 1);

  const freshBrowser = createHarness({sessionStore: {}, localStore: {}, initialTabs});
  await freshBrowser.tick(40);
  freshBrowser.fromApp({event: 'context', live_tracking: false, champion: 'aatrox'});
  await freshBrowser.tick(20);
  freshBrowser.fromApp({id: 'close2', command: 'close'});
  await freshBrowser.tick(150);
  const close2 = freshBrowser.port.posted.find(m => m.reply_to === 'close2');
  assert.equal(close2.closed, 1); // 2.4: every Lolalytics tab closes, managed or not
});

test('bridge_status false keeps native port and recovers with later context', async () => {
  const h = createHarness();
  await h.tick(40);
  assert.equal(h.connectCalls(), 1);

  h.fromApp({event: 'context', live_tracking: false, champion: 'aatrox'});
  await h.tick(20);
  h.fromApp({id: 'open-a', command: 'open', kind: 'base', url: 'https://lolalytics.com/lol/aatrox/build/?tier=all'});
  await h.tick(120);
  assert.equal(h.tabs.length, 1);

  h.fromApp({event: 'bridge_status', connected: false});
  await h.tick(20);
  h.fromApp({id: 'close-offline', command: 'close'});
  await h.tick(150);
  assert.equal(h.api.tabs._removes.length, 0);
  assert.equal(h.tabs.length, 1);
  assert.equal(h.connectCalls(), 1);

  h.fromApp({event: 'context', live_tracking: false, champion: 'aatrox'});
  await h.tick(20);
  h.fromApp({id: 'close-recovered', command: 'close'});
  await h.tick(180);
  const okReply = h.port.posted.find(m => m.reply_to === 'close-recovered');
  assert.equal(okReply.ok, true);
  assert.equal(okReply.closed, 1);
});

test('snapshot saves tabs, never removes, and aborts on save failure', async () => {
  const h = createHarness();
  await h.tick(40);
  h.fromApp({event: 'context', live_tracking: false, champion: 'aatrox'});
  await h.tick(20);
  h.fromApp({id: 'open-snap', command: 'open', kind: 'base', url: 'https://lolalytics.com/lol/aatrox/build/?tier=all'});
  await h.tick(120);

  h.fromApp({id: 'snapshot-ok', command: 'snapshot'});
  await h.tick(180);
  const ok = h.port.posted.find(m => m.reply_to === 'snapshot-ok');
  assert.equal(ok.ok, true);
  assert.equal(h.api.tabs._removes.length, 0);
  assert.equal(h.tabs.length, 1);

  h.setAckMode('fail');
  h.fromApp({id: 'snapshot-fail', command: 'snapshot'});
  await h.tick(180);
  const fail = h.port.posted.find(m => m.reply_to === 'snapshot-fail');
  assert.equal(fail.ok, false);
  assert.equal(h.api.tabs._removes.length, 0);
  assert.equal(h.tabs.length, 1);
});
