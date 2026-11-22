// Minimal, dependency-free Markdown to HTML renderer (headings, lists, tables, code, quotes, links).
const esc = (s) => s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
const inline = (s) => {
  const codes = [];
  s = s.replace(/`([^`]+)`/g, (_, c) => `\u0000${codes.push(esc(c)) - 1}\u0000`);
  s = esc(s)
    .replace(/!\[([^\]]*)\]\(([^)\s]+)[^)]*\)/g, '<img alt="$1" src="$2">')
    .replace(/\[([^\]]+)\]\(([^)\s]+)[^)]*\)/g, '<a href="$2">$1</a>')
    .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
    .replace(/__([^_]+)__/g, "<strong>$1</strong>")
    .replace(/(^|[^*\w])\*([^*\s][^*]*)\*/g, "$1<em>$2</em>");
  return s.replace(/\u0000(\d+)\u0000/g, (_, i) => `<code>${codes[i]}</code>`);
};
const cells = (row) => row.trim().replace(/^\||\|$/g, "").split("|").map((c) => c.trim());

const SEP = /^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$/;

export function parse(src) {
  const lines = src.replace(/\r\n?/g, "\n").split("\n");
  const out = [];
  let i = 0;
  while (i < lines.length) {
    const line = lines[i];
    let m;
    if (/^\s*$/.test(line)) { i++; continue; }
    if ((m = line.match(/^\s*(```|~~~)\s*([\w-]*)/))) {
      const fence = m[1], body = [];
      i++;
      while (i < lines.length && !lines[i].trim().startsWith(fence)) body.push(lines[i++]);
      i++;
      out.push(`<pre><code${m[2] ? ` class="language-${m[2]}"` : ""}>${esc(body.join("\n"))}</code></pre>`);
      continue;
    }
    if ((m = line.match(/^(#{1,6})\s+(.*?)\s*#*\s*$/))) {
      const n = m[1].length, id = m[2].toLowerCase().replace(/[^\w\s-]/g, "").trim().replace(/\s+/g, "-");
      out.push(`<h${n} id="${id}">${inline(m[2])}</h${n}>`); i++; continue;
    }
    if (/^\s*([-*_])(\s*\1){2,}\s*$/.test(line)) { out.push("<hr>"); i++; continue; }
    if (line.includes("|") && i + 1 < lines.length && SEP.test(lines[i + 1])) {
      const head = cells(line); i += 2;
      const rows = [];
      while (i < lines.length && lines[i].includes("|") && lines[i].trim()) rows.push(cells(lines[i++]));
      out.push(`<table><thead><tr>${head.map((c) => `<th>${inline(c)}</th>`).join("")}</tr></thead><tbody>${rows
        .map((r) => `<tr>${r.map((c) => `<td>${inline(c)}</td>`).join("")}</tr>`).join("")}</tbody></table>`);
      continue;
    }
    if (/^\s*>/.test(line)) {
      const body = [];
      while (i < lines.length && /^\s*>/.test(lines[i])) body.push(lines[i++].replace(/^\s*>\s?/, ""));
      out.push(`<blockquote>${parse(body.join("\n"))}</blockquote>`); continue;
    }
    if ((m = line.match(/^(\s*)([-*+]|\d+[.)])\s+/))) {
      const ordered = /\d/.test(m[2]), items = [];
      while (i < lines.length && (m = lines[i].match(/^(\s*)([-*+]|\d+[.)])\s+(.*)$/))) {
        let text = m[3]; i++;
        while (i < lines.length && /^\s{2,}\S/.test(lines[i]) && !/^\s*([-*+]|\d+[.)])\s+/.test(lines[i])) text += " " + lines[i++].trim();
        items.push(`<li>${inline(text.replace(/^\[( |x)\]\s*/i, (_, x) => (x === " " ? "☐ " : "☑ ")))}</li>`);
      }
      const tag = ordered ? "ol" : "ul";
      out.push(`<${tag}>${items.join("")}</${tag}>`); continue;
    }
    const para = [];
    const isTable = (k) => lines[k].includes("|") && k + 1 < lines.length && SEP.test(lines[k + 1]);
    while (i < lines.length && lines[i].trim() && !isTable(i) && !/^(#{1,6}\s|\s*(```|~~~)|\s*>|\s*([-*+]|\d+[.)])\s+)/.test(lines[i])) para.push(lines[i++].trim());
    if (!para.length) para.push(lines[i++].trim());
    out.push(`<p>${inline(para.join(" "))}</p>`);
  }
  return out.join("\n");
}
