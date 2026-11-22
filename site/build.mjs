// Renders the repository README and docs/ markdown into a static HTML site in dist/.
import { readFileSync, writeFileSync, mkdirSync, readdirSync, rmSync, existsSync } from "node:fs";
import { join, basename, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { parse } from "./md.mjs";

const here = dirname(fileURLToPath(import.meta.url));
const root = join(here, "..");
const out = join(here, "dist");
rmSync(out, { recursive: true, force: true });
mkdirSync(out, { recursive: true });

const docsDir = join(root, "docs");
const docs = existsSync(docsDir)
  ? readdirSync(docsDir).filter((f) => f.endsWith(".md")).sort()
  : [];
const slug = (f) => basename(f, ".md").toLowerCase().replace(/[^a-z0-9]+/g, "-");
const title = (f) => basename(f, ".md").replace(/[_-]+/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());

// Rewrite links to docs/*.md so they point at the generated pages.
const fixLinks = (html) =>
  html.replace(/href="(?:\.\/|\.\.\/)?(?:docs\/)?([^"#/]+)\.md(#[^"]*)?"/g, (_, n, h = "") => `href="/${slug(n + ".md")}.html${h}"`);

const css = `
:root{--bg:#0f1419;--panel:#161d25;--ink:#e6edf3;--muted:#8b98a5;--accent:#e0a94a;--line:#26313d}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.65 "Iowan Old Style","Charter",Georgia,serif;display:grid;grid-template-columns:260px 1fr;min-height:100vh}
nav{background:var(--panel);border-right:1px solid var(--line);padding:28px 20px;position:sticky;top:0;height:100vh;overflow:auto;font-family:ui-sans-serif,system-ui,sans-serif;font-size:14px}
nav .brand{font:700 20px/1 ui-monospace,Menlo,monospace;color:var(--accent);letter-spacing:.04em;text-decoration:none;display:block;margin-bottom:6px}
nav small{color:var(--muted);display:block;margin-bottom:24px}
nav a{color:var(--ink);text-decoration:none;display:block;padding:5px 8px;border-radius:4px}nav a:hover,nav a.on{background:#1f2933;color:var(--accent)}
main{padding:48px 56px;max-width:920px}
h1,h2,h3{font-family:ui-sans-serif,system-ui,sans-serif;line-height:1.25}h1{font-size:2.1rem;border-bottom:2px solid var(--accent);padding-bottom:10px}h2{margin-top:2.2em;border-bottom:1px solid var(--line);padding-bottom:6px}
a{color:var(--accent)}code{font:13.5px ui-monospace,Menlo,monospace;background:#1c252f;padding:2px 5px;border-radius:3px}
pre{background:#0a0e12;border:1px solid var(--line);padding:16px;overflow:auto;border-radius:6px}pre code{background:none;padding:0}
table{border-collapse:collapse;width:100%;margin:1em 0;font-size:14px;font-family:ui-sans-serif,system-ui,sans-serif}th,td{border:1px solid var(--line);padding:7px 10px;text-align:left}th{background:var(--panel)}
blockquote{border-left:3px solid var(--accent);margin:0;padding-left:16px;color:var(--muted)}
@media(max-width:800px){body{grid-template-columns:1fr}nav{position:static;height:auto}main{padding:28px 20px}}`;

const page = (name, body, active) => `<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>${name} · LedgerForge</title><style>${css}</style></head>
<body><nav><a class="brand" href="/">LEDGERFORGE</a><small>Payroll &amp; Accounting Engine</small>
<a href="/" class="${active === "index" ? "on" : ""}">Overview</a>
${docs.map((f) => `<a href="/${slug(f)}.html" class="${active === slug(f) ? "on" : ""}">${title(f)}</a>`).join("\n")}
</nav><main>${body}</main></body></html>`;

const render = (file) => fixLinks(parse(readFileSync(file, "utf8")));

writeFileSync(join(out, "index.html"), page("Overview", render(join(root, "README.md")), "index"));
for (const f of docs) writeFileSync(join(out, `${slug(f)}.html`), page(title(f), render(join(docsDir, f)), slug(f)));
writeFileSync(join(out, "404.html"), page("Not found", "<h1>Page not found</h1><p><a href='/'>Back to overview</a></p>", ""));
console.log(`Built ${docs.length + 1} pages into ${out}`);
