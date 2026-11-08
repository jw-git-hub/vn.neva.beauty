// Прогоняет строчный код Метрики на подставных объектах, затем «кликает» по ссылкам.
// Вход (stdin): {"script": "...", "events": [{type, button, link}]}, где link — null
// или {href, protocol, hostname, attrs: {имя: значение}}.
// Выход (stdout): JSON очереди вызовов ym, появившихся после init, то есть от кликов.
const vm = require("vm");

const PAGE_HOSTNAME = "vn.neva.beauty";

function makeLink(spec) {
  const attrs = spec.attrs || {};
  return {
    href: spec.href, protocol: spec.protocol, hostname: spec.hostname,
    getAttribute: (name) => (name in attrs ? attrs[name] : null),
    hasAttribute: (name) => name in attrs,
  };
}

function makeEvent(spec) {
  const link = spec.link ? makeLink(spec.link) : null;
  return { type: spec.type, button: spec.button, target: { closest: () => link } };
}

function run({ script, events }) {
  const handlers = {};
  const document = { readyState: "loading", scripts: [], head: { appendChild() {} },
    title: "Page", documentElement: { lang: "en" }, referrer: "",
    addEventListener: (type, handler) => { (handlers[type] = handlers[type] || []).push(handler); } };
  const context = vm.createContext({ document, sessionStorage: { getItem: () => null, removeItem() {} },
    addEventListener() {}, setTimeout() {}, Date, location: { hostname: PAGE_HOSTNAME,
      href: "https://" + PAGE_HOSTNAME + "/" } });
  context.window = context;
  vm.runInContext(script, context);
  const before = Array.from(context.ym.a || []).length;
  events.forEach((spec) => {
    (handlers[spec.type] || []).forEach((handler) => handler(makeEvent(spec)));
  });
  return Array.from(context.ym.a || []).slice(before).map((args) => Array.from(args));
}

let raw = "";
process.stdin.on("data", (chunk) => { raw += chunk; });
process.stdin.on("end", () => {
  process.stdout.write(JSON.stringify(run(JSON.parse(raw))));
});
