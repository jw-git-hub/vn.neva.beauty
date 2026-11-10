// Прогоняет цепочку строчных скриптов страницы на подставных объектах браузера с общим
// хранилищем: переход по языку, страж источника, запоминание клика по переключателю.
// Вход (stdin): {"session": {...}, "local": {...}, "steps": [{script, pathname, now,
// referrer, userAgent, languages, withoutUrl, storageThrows, click: {lang}}]}.
// Выход (stdout): {"session", "local" — что осталось; "steps": [{replacedWith}]}.
const vm = require("vm");

function makeStorage(initial, throws) {
  const store = { ...initial };
  const fail = () => { if (throws) { throw new Error("storage blocked"); } };
  return {
    store,
    getItem(name) { fail(); return name in store ? store[name] : null; },
    setItem(name, value) { fail(); store[name] = String(value); },
    removeItem(name) { fail(); delete store[name]; },
  };
}

function makeContext(step, session, local, result) {
  const listeners = [];
  const location = { host: "vn.neva.beauty", pathname: step.pathname, search: "", hash: "",
    replace(url) { result.replacedWith = url; } };
  const document = { referrer: step.referrer || "", addEventListener(type, handler) {
    if (type === "click") { listeners.push(handler); }
  } };
  const context = { location, document, sessionStorage: session, localStorage: local,
    Date: { now: () => step.now }, navigator: { userAgent: step.userAgent || "Safari",
      languages: step.languages || ["en"], language: "en" } };
  if (!step.withoutUrl) { context.URL = URL; }
  return { context: vm.createContext(context), listeners };
}

function clickEvent(lang) {
  const link = { getAttribute: (name) => (name === "data-lang" ? lang : null) };
  return { target: { closest: (selector) => (selector === "[data-lang]" ? link : null) } };
}

function runStep(step, session, local) {
  const result = { replacedWith: null };
  const { context, listeners } = makeContext(
    step, step.storageThrows ? makeStorage({}, true) : session,
    step.storageThrows ? makeStorage({}, true) : local, result);
  vm.runInContext(step.script, context);
  if (step.click) { listeners.forEach((handler) => handler(clickEvent(step.click.lang))); }
  return result;
}

let raw = "";
process.stdin.on("data", (chunk) => { raw += chunk; });
process.stdin.on("end", () => {
  const input = JSON.parse(raw);
  const session = makeStorage(input.session || {}, false);
  const local = makeStorage(input.local || {}, false);
  const steps = input.steps.map((step) => runStep(step, session, local));
  process.stdout.write(JSON.stringify({ session: session.store, local: local.store, steps }));
});
