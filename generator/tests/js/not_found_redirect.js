// Прогоняет строчный скрипт корневой 404 на подставных location, document и sessionStorage.
// Вход (stdin): {"script": "...", "pathnames": ["/en/x/", ...], "referrer": "...",
// "storageThrows": false}. Выход (stdout): по путям {"target": адрес перехода или null,
// "store": что записано в sessionStorage}.
const vm = require("vm");

function run(script, pathname, referrer, storageThrows) {
  const result = { target: null, store: {} };
  const location = { pathname, replace(url) { result.target = url; } };
  const sessionStorage = { setItem(name, value) {
    if (storageThrows) { throw new Error("storage blocked"); }
    result.store[name] = value;
  } };
  const document = { referrer };
  vm.runInContext(script, vm.createContext({ location, document, sessionStorage }));
  return result;
}

let raw = "";
process.stdin.on("data", (chunk) => { raw += chunk; });
process.stdin.on("end", () => {
  const { script, pathnames, referrer = "", storageThrows = false } = JSON.parse(raw);
  process.stdout.write(JSON.stringify(
    pathnames.map((pathname) => run(script, pathname, referrer, storageThrows))));
});
