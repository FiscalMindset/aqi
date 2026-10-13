/**
 * Every t("...") key used in src/ must exist in BOTH locales.
 *
 * A missing key does not fail the build: i18next renders the key itself, so the
 * page quietly shows the literal text "subscribe.place" to a user. That shipped
 * once already. This is the check that stops it shipping twice.
 */

// node builtins: this file is a vitest (node) test, and it is excluded from the
// browser tsconfig, which has no node types on purpose.
import { readdirSync, readFileSync, statSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import en from "../../src/i18n/en.json";
import hi from "../../src/i18n/hi.json";

const HERE = dirname(fileURLToPath(import.meta.url));
const SRC = join(HERE, "..", "..", "src");

function walk(dir: string): string[] {
  return readdirSync(dir).flatMap((entry) => {
    const full = join(dir, entry);
    if (entry === "i18n") return [];
    return statSync(full).isDirectory() ? walk(full) : [full];
  });
}

/** Literal t("key") and t('key') / t(`key`) calls. Skips template-literal keys. */
function keysIn(file: string): string[] {
  const source = readFileSync(file, "utf8");
  const found: string[] = [];
  const re = /\bt\(\s*["'`]([a-zA-Z0-9_]+(?:\.[a-zA-Z0-9_]+)+)["'`]/g;
  for (const m of source.matchAll(re)) found.push(m[1]!);
  return found;
}

const get = (obj: unknown, path: string): unknown =>
  path.split(".").reduce<unknown>((acc, k) => (acc as Record<string, unknown>)?.[k], obj);

const sources = walk(SRC).filter((f) => /\.tsx?$/.test(f));
const used = [...new Set(sources.flatMap(keysIn))].sort();

describe("i18n", () => {
  it("finds translation keys in the source", () => {
    // Guards the guard: if this is empty the regex broke and the rest is vacuous.
    expect(used.length).toBeGreaterThan(20);
  });

  it.each(used)("%s exists in en.json", (key) => {
    expect(get(en, key), `missing en translation for ${key}`).toBeDefined();
  });

  it.each(used)("%s exists in hi.json", (key) => {
    expect(get(hi, key), `missing hi translation for ${key}`).toBeDefined();
  });

  it("en and hi define the same key sets", () => {
    const flatten = (o: unknown, prefix = ""): string[] =>
      Object.entries(o as Record<string, unknown>).flatMap(([k, v]) =>
        v && typeof v === "object"
          ? flatten(v, `${prefix}${k}.`)
          : [`${prefix}${k}`],
      );
    const enKeys = new Set(flatten(en));
    const hiKeys = new Set(flatten(hi));
    const onlyEn = [...enKeys].filter((k) => !hiKeys.has(k));
    const onlyHi = [...hiKeys].filter((k) => !enKeys.has(k));
    expect({ onlyEn, onlyHi }).toEqual({ onlyEn: [], onlyHi: [] });
  });
});