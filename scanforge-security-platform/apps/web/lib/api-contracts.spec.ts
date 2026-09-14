import { execFile } from "node:child_process";
import { mkdtemp, readFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { promisify } from "node:util";

import { describe, expect, it } from "vitest";

const execFileAsync = promisify(execFile);

// Paths are resolved from the apps/web package root (vitest runs with that cwd).
const openapiUrl = resolve(process.cwd(), "../api/openapi.json");
const apiTypesUrl = resolve(process.cwd(), "lib/api-types.ts");
const apiClientUrl = resolve(process.cwd(), "lib/api.ts");

const spec = JSON.parse(await readFile(openapiUrl, "utf8")) as {
  paths: Record<string, Record<string, unknown>>;
};

/**
 * Normalizes a client path or spec path to a comparable shape:
 * - strips the `/api/v1` prefix and query strings,
 * - collapses `{param}` placeholders and `${...}` interpolations to `{}`,
 * - strips trailing slashes (FastAPI answers the no-slash form with a 307 redirect).
 */
function normalizePath(raw: string): string {
  let p = raw.replace(/\$\{[^}]*\}/g, "{}");
  const queryStart = p.indexOf("?");
  if (queryStart !== -1) p = p.slice(0, queryStart);
  p = p.replace(/\{[^}]*\}/g, "{}");
  if (p.startsWith("/api/v1/")) p = p.slice("/api/v1".length);
  while (p.endsWith("{}")) p = p.slice(0, -2);
  while (p.length > 1 && p.endsWith("/")) p = p.slice(0, -1);
  return p;
}

/** Returns the first top-level argument text of a call argument list. */
function firstArgument(inner: string): string {
  let depth = 0;
  let quote: string | null = null;
  for (let i = 0; i < inner.length; i++) {
    const ch = inner[i];
    if (quote) {
      if (ch === quote) quote = null;
      continue;
    }
    if (ch === "`" || ch === '"' || ch === "'") {
      quote = ch;
      continue;
    }
    if ("([{".includes(ch)) depth++;
    else if (")]}".includes(ch)) depth--;
    else if (ch === "," && depth === 0) return inner.slice(0, i);
  }
  return inner;
}

/** Extracts every `request(...)` / `request<T>(...)` call site from the typed API client. */
function extractClientCalls(source: string): Array<{ path: string; method: string }> {
  const calls: Array<{ path: string; method: string }> = [];
  const callStart = /\brequest(?:<[^>(]*>)?\(/g;
  for (let match = callStart.exec(source); match !== null; match = callStart.exec(source)) {
    let depth = 0;
    let end = match.index + match[0].length - 1;
    for (; end < source.length; end++) {
      const ch = source[end];
      if (ch === "(") depth++;
      else if (ch === ")") {
        depth--;
        if (depth === 0) break;
      }
    }
    const callText = source.slice(match.index, end + 1);
    const genericPrefix = callText.match(/^request<[^>(]*>\(/)?.[0].length ?? "request(".length;
    const inner = callText.slice(genericPrefix, callText.length - 1);
    let rawPath = firstArgument(inner).trim();
    if (rawPath.startsWith("`")) rawPath = rawPath.slice(1, rawPath.lastIndexOf("`"));
    else rawPath = rawPath.slice(1, -1);
    const methodMatch = callText.match(/method:\s*"([A-Za-z]+)"/);
    if (rawPath.startsWith("/")) {
      calls.push({
        path: rawPath,
        method: (methodMatch?.[1] ?? "GET").toUpperCase(),
      });
    }
  }
  return calls;
}

/** Like normalizePath but keeps the trailing slash, so exact spec-route matches are distinguishable. */
function normalizeKeepSlash(raw: string): string {
  let p = raw.replace(/\$\{[^}]*\}/g, "{}");
  const queryStart = p.indexOf("?");
  if (queryStart !== -1) p = p.slice(0, queryStart);
  p = p.replace(/\{[^}]*\}/g, "{}");
  if (p.startsWith("/api/v1/")) p = p.slice("/api/v1".length);
  return p;
}

function specMethodExists(path: string, method: string): boolean {
  const normalized = normalizePath(path);
  for (const [specPath, ops] of Object.entries(spec.paths)) {
    if (normalizePath(specPath) !== normalized) continue;
    if (method.toLowerCase() in ops) return true;
  }
  return false;
}

/**
 * True when the client's URL hits the spec route literally (no trailing-slash
 * 307 redirect). `${qs ? ...}` conditionals leave a trailing `{}` artifact that
 * is not part of the requested URL, so that one form is also considered.
 */
function matchesSpecRouteExactly(path: string): boolean {
  const requested = normalizeKeepSlash(path);
  const withoutQueryArtifact = requested.replace(/\{\}$/, "");
  return Object.keys(spec.paths).some((specPath) => {
    const specRoute = normalizeKeepSlash(specPath);
    return specRoute === requested || specRoute === withoutQueryArtifact;
  });
}

/** Fails loudly with the first divergent line when the committed types drift. */
function expectTypesInSync(generated: string, committed: string): void {
  if (generated === committed) return;
  const genLines = generated.split("\n");
  const committedLines = committed.split("\n");
  let firstDiff = 0;
  while (
    firstDiff < genLines.length &&
    firstDiff < committedLines.length &&
    genLines[firstDiff] === committedLines[firstDiff]
  ) {
    firstDiff++;
  }
  const context = committedLines
    .slice(firstDiff, firstDiff + 3)
    .map((l) => `  committed:${firstDiff + 1}: ${l}`)
    .join("\n");
  throw new Error(
    `lib/api-types.ts is out of sync with apps/api/openapi.json (first diff at line ${firstDiff + 1}).\n` +
      `Run \`npm run gen:types\` in apps/web and commit the result.\n${context}`,
  );
}

describe("web/api contract parity", () => {
  it("lib/api-types.ts is byte-identical to generated types from ../api/openapi.json", async () => {
    // Runs the exact command behind `npm run gen:types` into a temp dir.
    const outDir = await mkdtemp(join(tmpdir(), "api-types-parity-"));
    try {
      const generatedPath = join(outDir, "api-types.ts");
      await execFileAsync(resolve(process.cwd(), "node_modules/.bin/openapi-typescript"), [
        openapiUrl,
        "-o",
        generatedPath,
      ]);
      const generated = await readFile(generatedPath, "utf8");
      const committed = await readFile(apiTypesUrl, "utf8");
      expectTypesInSync(generated, committed);
    } finally {
      await rm(outDir, { recursive: true, force: true });
    }
    expect((await readFile(apiTypesUrl, "utf8")).length).toBeGreaterThan(1000);
  });

  it("every path the web client calls exists in openapi.json with the HTTP method used", async () => {
    const clientCalls = extractClientCalls(await readFile(apiClientUrl, "utf8"));
    expect(clientCalls.length).toBeGreaterThan(30);

    const drift: string[] = [];
    const redirectDependent: string[] = [];
    for (const { path, method } of clientCalls) {
      const key = `${method} ${path}`;
      if (!specMethodExists(path, method)) {
        drift.push(key);
        continue;
      }
      if (!matchesSpecRouteExactly(path)) redirectDependent.push(key);
    }

    expect(drift).toEqual([]);

    // Stable, query-independent snapshot of the calls that resolve only through
    // FastAPI's trailing-slash 307 redirect. Review whenever this list changes:
    // prefer adding the spec's trailing slash to the client URL.
    const slashNormalized = redirectDependent.map((entry) => {
      const sep = entry.indexOf(" ");
      const method = entry.slice(0, sep);
      const rawPath = entry.slice(sep + 1);
      let p = normalizeKeepSlash(rawPath).replace(/\{\}$/, "");
      while (p.length > 1 && p.endsWith("/")) p = p.slice(0, -1);
      return `${method} ${p}`;
    });
    expect(slashNormalized.sort()).toEqual(
      [
        "GET /notifications",
        "GET /organizations",
        "GET /organizations/{}/projects",
        "GET /organizations/{}/projects/{}/exports",
        "GET /organizations/{}/projects/{}/findings",
        "GET /organizations/{}/projects/{}/repositories",
        "GET /organizations/{}/projects/{}/repositories/{}/schedules",
        "GET /organizations/{}/projects/{}/scans",
        "POST /organizations",
        "POST /organizations/{}/projects",
        "POST /organizations/{}/projects/{}/exports",
        "POST /organizations/{}/projects/{}/repositories",
        "POST /organizations/{}/projects/{}/repositories/{}/schedules",
        "POST /organizations/{}/projects/{}/scans",
      ].sort(),
    );
  });
});
