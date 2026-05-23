/* invest-signal-kit — i18n engine */
'use strict';

const I18n = (() => {
  const LOCALE_KEY = 'isk-locale';
  const locales = { en: EN, zh: ZH };
  let current = 'en';

  function getLocale() { return current; }

  function setLocale(locale) {
    current = locale;
    try { localStorage.setItem(LOCALE_KEY, locale); } catch (_) { /* noop */ }
    refreshDOM();
    updateLangSwitcherUI();
    if (typeof onLocaleChanged === 'function') onLocaleChanged(locale);
  }

  function getLang() {
    if (current === 'zh') return 'zh';
    if (current === 'bilingual') return 'bilingual';
    return 'en';
  }

  function isBilingual() { return current === 'bilingual'; }

  function t(key, fallback) {
    const en = (locales.en && locales.en[key]) || fallback || key;
    if (current === 'en') return en;
    if (current === 'zh') return (locales.zh && locales.zh[key]) || en;
    if (current === 'bilingual') {
      const zh = (locales.zh && locales.zh[key]) || '';
      return zh ? en + ' <span class="i18n-zh">(' + zh + ')</span>' : en;
    }
    return en;
  }

  function tPlain(key, fallback) {
    const en = (locales.en && locales.en[key]) || fallback || key;
    if (current === 'en') return en;
    if (current === 'zh') return (locales.zh && locales.zh[key]) || en;
    return en;
  }

  /* Update all elements with data-i18n attributes */
  function refreshDOM() {
    /* Text content */
    document.querySelectorAll('[data-i18n]').forEach(el => {
      const key = el.getAttribute('data-i18n');
      const translation = t(key);
      /* Preserve existing child elements (like icons) */
      if (el.children.length === 0) {
        el.innerHTML = translation;
      }
    });

    /* Placeholders */
    document.querySelectorAll('[data-i18n-placeholder]').forEach(el => {
      const key = el.getAttribute('data-i18n-placeholder');
      el.setAttribute('placeholder', tPlain(key));
    });

    /* Title attributes (tooltips) */
    document.querySelectorAll('[data-i18n-title]').forEach(el => {
      const key = el.getAttribute('data-i18n-title');
      el.setAttribute('title', tPlain(key));
    });

    /* Headers - only replace direct text nodes, preserve child elements */
    document.querySelectorAll('[data-i18n-header]').forEach(el => {
      const key = el.getAttribute('data-i18n-header');
      /* Save children (like btn-groups) */
      const children = Array.from(el.children);
      el.innerHTML = t(key);
      /* If the translation created text, prepend children back? No — for headers with buttons,
         the text is typically a single text node. We replace the whole content. */
    });

    document.dispatchEvent(new CustomEvent('i18n-refreshed', { detail: { locale: current } }));
  }

  /* Update the language switcher dropdown to reflect current selection */
  function updateLangSwitcherUI() {
    const sel = document.getElementById('lang-select');
    if (!sel) return;
    sel.value = current;
    // Update option labels to show language names in their own language
    const optionLabels = { en: 'English', zh: '中文', bilingual: '双语' };
    for (const opt of sel.options) {
      opt.textContent = optionLabels[opt.value] || opt.value;
    }
  }

  /* Initialize from localStorage or default */
  function init() {
    let saved = 'en';
    try { saved = localStorage.getItem(LOCALE_KEY) || 'en'; } catch (_) { /* noop */ }
    if (!locales[saved]) saved = 'en';
    current = saved;
    document.addEventListener('DOMContentLoaded', () => {
      updateLangSwitcherUI();
      refreshDOM();
    });
    if (document.readyState !== 'loading') {
      updateLangSwitcherUI();
      refreshDOM();
    }
    return current;
  }

  return { init, t, tPlain, getLocale, setLocale, getLang, isBilingual, refreshDOM };
})();

// Auto-initialize when scripts are loaded
I18n.init();
