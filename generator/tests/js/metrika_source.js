// Прогоняет строчный код Метрики на подставных объектах и печатает очередь вызовов ym.
// Вход (stdin): {"script": "...", "source": адрес-источник или null}.
// Выход (stdout): {"calls": [[аргументы ym]...], "referrer": document.referrer после
// кода, "left": что осталось в sessionStorage}. До кода referrer — наша русская страница.
const vm = require("vm");

let raw = "";
process.stdin.on("data", (chunk) => { raw += chunk; });
process.stdin.on("end", () => {
  const { script, source, key } = JSON.parse(raw);
  const store = source === null ? {} : { [key]: source };
  const sessionStorage = {
    getItem: (name) => (name in store ? store[name] : null),
    removeItem: (name) => { delete store[name]; },
  };
  const document = { readyState: "loading", scripts: [], head: { appendChild() {} },
    title: "Page", addEventListener() {}, documentElement: { lang: "en" },
    referrer: "https://vn.neva.beauty/lpg-massazh/" };
  const context = vm.createContext({ document, sessionStorage, addEventListener() {},
    setTimeout() {}, Date, location: { href: "https://vn.neva.beauty/en/" } });
  context.window = context;
  vm.runInContext(script, context);
  const calls = Array.from(context.ym.a || []).map((args) => Array.from(args));
  process.stdout.write(JSON.stringify({ calls, referrer: document.referrer,
    left: store[key] === undefined ? null : store[key] }));
});
