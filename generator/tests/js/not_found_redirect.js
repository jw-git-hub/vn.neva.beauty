// Прогоняет строчный скрипт корневой 404 на подставном location.
// Вход (stdin): {"script": "...", "pathnames": ["/en/x/", ...]}.
// Выход (stdout): [адрес перехода или null] по путям.
const vm = require("vm");

function run(script, pathname) {
  const result = { target: null };
  const location = { pathname, replace(url) { result.target = url; } };
  vm.runInContext(script, vm.createContext({ location }));
  return result.target;
}

let raw = "";
process.stdin.on("data", (chunk) => { raw += chunk; });
process.stdin.on("end", () => {
  const { script, pathnames } = JSON.parse(raw);
  process.stdout.write(JSON.stringify(pathnames.map((pathname) => run(script, pathname))));
});
