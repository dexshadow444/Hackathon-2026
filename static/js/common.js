/* ==========================================================================
   JM VERTEX HACKATHON 2027 · SHARED CLIENT ENGINE
   High-performance, secure, XSS-safe DOM & API manipulation
   ========================================================================== */

window.HK = (() => {
  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

  function el(tag, props = {}, ...kids) {
    const node = document.createElement(tag);
    for (const [k, v] of Object.entries(props)) {
      if (k === "class") node.className = v;
      else if (k === "text") node.textContent = v;
      else if (k === "html") node.innerHTML = v;
      else node.setAttribute(k, v);
    }
    kids.flat().forEach((c) => {
      if (c == null) return;
      if (typeof c === "string" || typeof c === "number") {
        node.appendChild(document.createTextNode(String(c)));
      } else {
        node.appendChild(c);
      }
    });
    return node;
  }

  const fmt = (iso, opts) => {
    try {
      return new Intl.DateTimeFormat("en-IN", { timeZone: "Asia/Kolkata", ...opts }).format(new Date(iso));
    } catch {
      return iso;
    }
  };

  const DATE = { day: "numeric", month: "short", year: "numeric" };
  const DATETIME = { day: "numeric", month: "short", year: "numeric", hour: "numeric", minute: "2-digit", hour12: true };

  async function getJSON(url) {
    const headers = { Accept: "application/json" };
    try {
      const token = localStorage.getItem("hackathon_admin_token");
      if (token) headers["Authorization"] = `Bearer ${token}`;
    } catch {}
    const res = await fetch(url, { headers, credentials: "include" });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw err;
    }
    return res.json();
  }

  async function postJSON(url, data) {
    const headers = { "Content-Type": "application/json", Accept: "application/json" };
    try {
      const token = localStorage.getItem("hackathon_admin_token");
      if (token) headers["Authorization"] = `Bearer ${token}`;
    } catch {}
    const res = await fetch(url, {
      method: "POST",
      headers,
      credentials: "include",
      body: JSON.stringify(data),
    });
    const json = await res.json().catch(() => ({}));
    if (!res.ok) throw json;
    return json;
  }

  function setLoading(btn, on) {
    if (!btn) return;
    btn.disabled = on;
    btn.classList.toggle("is-loading", on);
    btn.setAttribute("aria-busy", String(on));
  }

  function clearErrors(form) {
    if (!form) return;
    form.querySelectorAll(".field-error").forEach((p) => (p.textContent = ""));
    form.querySelectorAll(".field.has-error").forEach((f) => f.classList.remove("has-error"));
  }

  function showFieldErrors(form, errors) {
    if (!form || !errors) return;
    let first = null;
    for (const [name, msg] of Object.entries(errors)) {
      const p = form.querySelector(`#err-${CSS.escape(name)}`) || form.querySelector(`[data-error-for="${CSS.escape(name)}"]`);
      if (p) {
        p.textContent = msg;
        p.closest(".field")?.classList.add("has-error");
      }
      if (!first) {
        first = form.querySelector(`[name="${CSS.escape(name)}"]`);
      }
    }
    if (first) first.focus();
  }

  function countdownParts(ms) {
    const s = Math.max(0, Math.floor(ms / 1000));
    return {
      d: Math.floor(s / 86400),
      h: Math.floor((s % 86400) / 3600),
      m: Math.floor((s % 3600) / 60),
      s: s % 60,
    };
  }

  /* Futuristic Preloader (Insane-Preloader inspired numerical counter) */
  function initPreloader(onComplete) {
    const preloader = $("#preloader");
    const countEl = $("#preloaderCount");
    const fillEl = $("#preloaderBar");
    if (!preloader || !countEl) {
      if (onComplete) onComplete();
      return;
    }

    let progress = 0;
    const startTime = performance.now();
    const duration = 1200; // 1.2s smooth high-tech roll

    function step(now) {
      const elapsed = now - startTime;
      progress = Math.min(100, Math.floor((elapsed / duration) * 100));

      countEl.textContent = String(progress).padStart(2, "0");
      if (fillEl) fillEl.style.width = `${progress}%`;

      if (progress < 100) {
        requestAnimationFrame(step);
      } else {
        setTimeout(() => {
          preloader.classList.add("loaded");
          setTimeout(() => {
            preloader.remove();
            if (onComplete) onComplete();
          }, 900);
        }, 150);
      }
    }

    requestAnimationFrame(step);
  }

  /* Modal Management */
  function setupModal(modalId) {
    const modal = $(`#${modalId}`);
    if (!modal) return null;

    function open() {
      modal.classList.add("open");
      document.body.style.overflow = "hidden";
    }

    function close() {
      modal.classList.remove("open");
      document.body.style.overflow = "";
    }

    modal.querySelectorAll(".modal-close-trigger").forEach((b) => b.addEventListener("click", close));
    modal.addEventListener("click", (e) => {
      if (e.target === modal) close();
    });
    window.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && modal.classList.contains("open")) close();
    });

    return { open, close };
  }

  return {
    $,
    $$,
    el,
    fmt,
    DATE,
    DATETIME,
    getJSON,
    postJSON,
    setLoading,
    clearErrors,
    showFieldErrors,
    countdownParts,
    initPreloader,
    setupModal,
  };
})();
