class FakeStorage {
  constructor() { this.data = {}; }
  getItem(k) { return this.data[k] ?? null; }
  setItem(k, v) { this.data[k] = v; }
  removeItem(k) { delete this.data[k]; }
}
global.sessionStorage = new FakeStorage();
const { createStore: create } = await import('zustand/vanilla');
const { persist } = await import('zustand/middleware');

const storageAdapter = {
  getItem: (name) => { const v = sessionStorage.getItem(name); return v ? JSON.parse(v) : null; },
  setItem: (name, value) => sessionStorage.setItem(name, JSON.stringify(value)),
  removeItem: (name) => sessionStorage.removeItem(name),
};

const store1 = create()(persist((set) => ({
  messages: [], input: '',
  setMessages: (u) => set((s) => ({ messages: typeof u === 'function' ? u(s.messages) : u })),
  setInput: (i) => set({ input: i }),
}), { name: 'nexa-workbench-session', storage: storageAdapter }));

store1.getState().setInput('unsent draft about valve 42');
store1.getState().setMessages((p) => [...p, {id:'1', role:'user', content:'what is Q3 revenue'}]);
store1.getState().setMessages((p) => [...p, {id:'2', role:'assistant', content:'2400 crore'}]);

const store2 = create()(persist((set) => ({
  messages: [], input: '',
  setMessages: (u) => set((s) => ({ messages: typeof u === 'function' ? u(s.messages) : u })),
  setInput: (i) => set({ input: i }),
}), { name: 'nexa-workbench-session', storage: storageAdapter }));

await new Promise(r => setTimeout(r, 50));
const s = store2.getState();
console.log('messages:', s.messages.length, 'input:', JSON.stringify(s.input));
if (s.messages.length === 2 && s.input === 'unsent draft about valve 42') {
  console.log('PASS');
} else {
  console.log('FAIL');
  process.exit(1);
}
