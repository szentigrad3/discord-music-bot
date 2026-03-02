import { createRequire } from 'module';
import { fileURLToPath } from 'url';
import path from 'path';
import { readFileSync } from 'fs';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

const locales = {};

function loadLocale(lang) {
  if (locales[lang]) return locales[lang];
  try {
    const raw = readFileSync(path.join(__dirname, 'locales', `${lang}.json`), 'utf8');
    locales[lang] = JSON.parse(raw);
    return locales[lang];
  } catch {
    return null;
  }
}

// Pre-load known locales
loadLocale('en');
loadLocale('es');

/**
 * Get a translated string.
 * @param {string} key   Dot-separated key, e.g. "errors.notInVoice"
 * @param {string} lang  Language code, e.g. "en"
 * @param {Record<string, string|number>} [vars]  Replacements for {{varName}}
 * @returns {string}
 */
export function t(key, lang = 'en', vars = {}) {
  const locale = loadLocale(lang) ?? loadLocale('en');
  const fallback = loadLocale('en');

  const resolve = (obj, parts) => {
    let cur = obj;
    for (const part of parts) {
      if (cur == null) return null;
      cur = cur[part];
    }
    return typeof cur === 'string' ? cur : null;
  };

  const parts = key.split('.');
  let str = resolve(locale, parts) ?? resolve(fallback, parts) ?? key;

  for (const [k, v] of Object.entries(vars)) {
    str = str.replaceAll(`{{${k}}}`, String(v));
  }

  return str;
}
