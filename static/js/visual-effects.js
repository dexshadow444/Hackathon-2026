/**
 * JM Vertex Hackathon 2027 · Award-Winning Interactions & 3D Parallax System
 * Inspired by Made-In-Webflow 3D Animation Showcase
 */
(() => {
  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const finePointer = window.matchMedia("(hover: hover) and (pointer: fine)").matches;

  // 1. Custom Cyber Glowing Cursor
  if (finePointer && !reduceMotion) {
    const cursorDot = document.createElement("div");
    cursorDot.className = "cursor-dot";
    const cursorRing = document.createElement("div");
    cursorRing.className = "cursor-ring";
    document.body.appendChild(cursorDot);
    document.body.appendChild(cursorRing);

    let mouseX = -100;
    let mouseY = -100;
    let ringX = -100;
    let ringY = -100;

    window.addEventListener("pointermove", (e) => {
      mouseX = e.clientX;
      mouseY = e.clientY;
      cursorDot.style.transform = `translate3d(${mouseX}px, ${mouseY}px, 0)`;
    }, { passive: true });

    function renderCursor() {
      ringX += (mouseX - ringX) * 0.15;
      ringY += (mouseY - ringY) * 0.15;
      cursorRing.style.transform = `translate3d(${ringX}px, ${ringY}px, 0)`;
      requestAnimationFrame(renderCursor);
    }
    requestAnimationFrame(renderCursor);

    // Expand cursor on interactive elements
    const interactives = "a, button, input, select, textarea, .track-card, .glass-panel, .ticket-card, summary";
    document.querySelectorAll(interactives).forEach((el) => {
      el.addEventListener("mouseenter", () => cursorRing.classList.add("is-hovered"));
      el.addEventListener("mouseleave", () => cursorRing.classList.remove("is-hovered"));
    });
  }

  // 2. 3D Card Tilt with Specular Spotlight Tracking
  if (finePointer && !reduceMotion) {
    const spotlightCards = document.querySelectorAll(
      ".track-card, .ticket-card, .glass-panel, .notice-banner, .metric-card, .crew-member-card, .hud-chip"
    );

    spotlightCards.forEach((card) => {
      card.addEventListener("pointermove", (e) => {
        const rect = card.getBoundingClientRect();
        const x = e.clientX - rect.left;
        const y = e.clientY - rect.top;

        // Spotlight CSS Variables
        card.style.setProperty("--mouse-x", `${x}px`);
        card.style.setProperty("--mouse-y", `${y}px`);

        // 3D Perspective Tilt (-10deg to +10deg)
        const centerX = rect.width / 2;
        const centerY = rect.height / 2;
        const rotateX = ((y - centerY) / centerY) * -8;
        const rotateY = ((x - centerX) / centerX) * 8;

        card.style.setProperty("--tilt-rx", `${rotateX.toFixed(2)}deg`);
        card.style.setProperty("--tilt-ry", `${rotateY.toFixed(2)}deg`);
      }, { passive: true });

      card.addEventListener("pointerleave", () => {
        card.style.setProperty("--tilt-rx", "0deg");
        card.style.setProperty("--tilt-ry", "0deg");
      });
    });
  }

  // 3. Parallax Floating Elements in Hero
  if (finePointer && !reduceMotion) {
    const hero = document.querySelector(".hero");
    const floatingChips = document.querySelectorAll(".hud-chip, .live-count-badge");

    if (hero) {
      window.addEventListener("pointermove", (e) => {
        const w = window.innerWidth;
        const h = window.innerHeight;
        const offsetX = (e.clientX - w / 2) / (w / 2);
        const offsetY = (e.clientY - h / 2) / (h / 2);

        floatingChips.forEach((chip, i) => {
          const depth = (i + 1) * 8;
          chip.style.transform = `translate3d(${offsetX * depth}px, ${offsetY * depth}px, 0)`;
        });
      }, { passive: true });
    }
  }

  // 4. Staggered Scroll Reveal Observer
  if (!reduceMotion && "IntersectionObserver" in window) {
    const revealTargets = document.querySelectorAll(
      ".section-head, .track-card, .timeline-item, .glass-panel, .faq-item, .split-grid > div"
    );

    const observer = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          entry.target.classList.add("is-revealed");
          observer.unobserve(entry.target);
        }
      });
    }, { threshold: 0.12, rootMargin: "0px 0px -40px 0px" });

    revealTargets.forEach((el, index) => {
      el.classList.add("reveal-element");
      el.style.setProperty("--stagger-delay", `${(index % 4) * 80}ms`);
      observer.observe(el);
    });
  }

  // 5. Ambient Cyber Audio Effects (Synthesizer Soundscape)
  try {
    const AudioContext = window.AudioContext || window.webkitAudioContext;
    if (AudioContext) {
      let ctx = null;
      let soundEnabled = false;

      const soundToggleBtn = document.getElementById("soundToggleBtn");
      if (soundToggleBtn) {
        soundToggleBtn.addEventListener("click", () => {
          if (!ctx) ctx = new AudioContext();
          if (ctx.state === "suspended") ctx.resume();

          soundEnabled = !soundEnabled;
          soundToggleBtn.classList.toggle("is-active", soundEnabled);
          soundToggleBtn.setAttribute("aria-pressed", String(soundEnabled));
          soundToggleBtn.title = soundEnabled ? "Cyber Audio Enabled (Click to Mute)" : "Muted (Click to Enable Audio)";
          playBeep(soundEnabled ? 880 : 330, 0.08);
        });
      }

      function playBeep(freq = 600, duration = 0.06) {
        if (!soundEnabled || !ctx) return;
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.type = "sine";
        osc.frequency.setValueAtTime(freq, ctx.currentTime);
        gain.gain.setValueAtTime(0.04, ctx.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + duration);
        osc.connect(gain);
        gain.connect(ctx.destination);
        osc.start();
        osc.stop(ctx.currentTime + duration);
      }

      // Add soft tick sounds to clicks
      document.addEventListener("click", (e) => {
        if (e.target.closest("button, a, .track-card, summary")) {
          playBeep(720, 0.05);
        }
      }, { passive: true });
    }
  } catch (err) {}
})();
