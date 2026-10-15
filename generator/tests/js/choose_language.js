// Прогоняет строчный скрипт выбора языка на подставных объектах браузера.
// Вход (stdin): {"script": "...", "cases": [{languages, saved, referrer, userAgent,
// search, hash, storageFails}]}. Выход (stdout): [адрес перехода или null] по случаям.
const vm = require("vm");

function storage(value, fails) {
  return {
    getItem() { if (fails) throw new Error("denied"); return value; },
    setItem() { if (fails) throw new Error("denied"); },
  };
}

function run(script, input) {
  const result = { target: null, assigned: false };
  const location = {
    host: "vn.neva.beauty", search: input.search || "", hash: input.hash || "",
    replace(url) { result.target = url; },
  };
  Object.defineProperty(location, "href", { set() { result.assigned = true; } });
  const context = vm.createContext({
    navigator: { languages: input.languages, language: input.language || input.languages[0],
      userAgent: input.userAgent },
    document: { referrer: input.referrer },
    location, URL,
    localStorage: storage(input.saved, input.storageFails),
    sessionStorage: storage(null, input.storageFails),
  });
  vm.runInContext(script, context);
  return result.assigned ? "ASSIGNED" : result.target;
}

let raw = "";
process.stdin.on("data", (chunk) => { raw += chunk; });
process.stdin.on("end", () => {
  const { script, cases } = JSON.parse(raw);
  process.stdout.write(JSON.stringify(cases.map((input) => run(script, input))));
});
