export type UnifiedFile = { path: string; name: string; bytes: number; searchable: boolean; reason?: string; url: string };
export type UnifiedHit = { file: string; path: string; line: number; snippet: string };
export type UnifiedSearchProgress = { file: string; index: number; total: number; hits: number };

const MANIFEST_URL = `${import.meta.env.BASE_URL}unified-search/files.json`;
let manifestPromise: Promise<UnifiedFile[]> | undefined;

export async function getUnifiedFiles() {
  manifestPromise ??= fetch(MANIFEST_URL, { cache: "no-cache" }).then(async response => {
    if (!response.ok) throw new Error("רשימת קובצי הדמו אינה זמינה באתר.");
    const files = await response.json() as UnifiedFile[];
    if (!Array.isArray(files)) throw new Error("רשימת הקבצים אינה תקינה.");
    return files;
  });
  return manifestPromise;
}

function normalize(value: string) { return value.toLocaleLowerCase("he"); }

async function searchFile(file: UnifiedFile, query: string, maxPerFile: number): Promise<UnifiedHit[]> {
  if (!file.searchable) return [];
  const response = await fetch(file.url, { cache: "no-store", credentials: "omit" });
  if (!response.ok || !response.body) return [];
  const reader = response.body.getReader();
  const decoder = new TextDecoder("utf-8", { fatal: false });
  const needle = normalize(query);
  let carry = "";
  let lineNumber = 0;
  const hits: UnifiedHit[] = [];
  while (true) {
    const { value, done } = await reader.read();
    const text = carry + decoder.decode(value ?? new Uint8Array(), { stream: !done });
    const lines = text.split(/\r?\n/);
    carry = done ? "" : (lines.pop() ?? "");
    for (const line of lines) {
      lineNumber += 1;
      if (normalize(line).includes(needle)) {
        hits.push({ file: file.name, path: file.path, line: lineNumber, snippet: line.trim().slice(0, 900) });
        if (hits.length >= maxPerFile) { await reader.cancel(); return hits; }
      }
    }
    if (done) break;
  }
  if (carry) {
    lineNumber += 1;
    if (normalize(carry).includes(needle)) hits.push({ file: file.name, path: file.path, line: lineNumber, snippet: carry.trim().slice(0, 900) });
  }
  return hits;
}

export async function searchAllUnifiedFiles(query: string, options: { maxHits?: number; maxPerFile?: number; onProgress?: (progress: UnifiedSearchProgress) => void } = {}) {
  const value = query.trim();
  if (value.length < 2) throw new Error("יש להזין לפחות שתי תווים לחיפוש.");
  const files = await getUnifiedFiles();
  const searchable = files.filter(file => file.searchable);
  const hits: UnifiedHit[] = [];
  const maxHits = options.maxHits ?? 100;
  for (let index = 0; index < searchable.length; index += 1) {
    if (hits.length >= maxHits) break;
    const file = searchable[index];
    try { hits.push(...(await searchFile(file, value, Math.min(options.maxPerFile ?? 8, maxHits - hits.length)))); } catch { /* continue with the next source */ }
    options.onProgress?.({ file: file.name, index: index + 1, total: searchable.length, hits: hits.length });
  }
  return { files, hits: hits.slice(0, maxHits), searchedFiles: searchable.length };
}
