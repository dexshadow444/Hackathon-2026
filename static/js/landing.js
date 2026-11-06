(() => {
  const {
    $,
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
  } = HK;

  const NOT_SURE = "Not sure yet";
  const pad = (n) => String(n).padStart(2, "0");

  function render(cfg) {
    const ev = cfg.event;
    document.title = `${ev.name} · Official Registration`;

    if ($("#brandName")) $("#brandName").textContent = ev.name;
    if ($("#heroTitle")) {
      const parts = ev.name.split(" ");
      const first = parts.slice(0, 2).join(" ");
      const rest = parts.slice(2).join(" ");
      $("#heroTitle").innerHTML = `${first} <span class="hero-title-accent">${rest}</span>`;
    }
    if ($("#tagline")) $("#tagline").textContent = ev.tagline;
    if ($("#heroDates")) $("#heroDates").textContent = `${fmt(ev.start, DATE)} – ${fmt(ev.end, DATE)}`;
    if ($("#heroVenue")) $("#heroVenue").textContent = ev.venue || ev.location || "Pollachi, Tamil Nadu";
    if ($("#heroOrganiser")) $("#heroOrganiser").textContent = `Organised by ${ev.organiser}`;
    if ($("#footerOrg")) $("#footerOrg").textContent = `© ${ev.organiser}. All rights reserved.`;

    if ($("#aboutText") && ev.about) {
      $("#aboutText").replaceChildren(...ev.about.map((t) => el("p", { text: t })));
    }

    if ($("#tlOpen") && cfg.timeline && cfg.timeline[0]) $("#tlOpen").textContent = fmt(cfg.timeline[0].at, DATETIME);
    if ($("#tlClose") && cfg.timeline && cfg.timeline[1]) $("#tlClose").textContent = fmt(cfg.timeline[1].at, DATETIME);
    if ($("#tlStart") && cfg.timeline && cfg.timeline[2]) $("#tlStart").textContent = fmt(cfg.timeline[2].at, DATETIME);
    if ($("#tlEnd") && cfg.timeline && cfg.timeline[3]) $("#tlEnd").textContent = fmt(cfg.timeline[3].at, DATETIME);

    const feePerMember = cfg.fee_per_member_inr || cfg.fee_inr || 99;
    if ($("#feeAmount")) $("#feeAmount").textContent = `₹${feePerMember}`;
    if ($("#factFee")) $("#factFee").textContent = `₹${feePerMember} per participant`;
    if ($("#factTeam")) $("#factTeam").textContent = `${cfg.team_size.min} to ${cfg.team_size.max} members`;
    if ($("#factDeadline")) $("#factDeadline").textContent = fmt(cfg.registration.deadline, DATE);

    if ($("#faqList") && cfg.faq) {
      $("#faqList").replaceChildren(
        ...cfg.faq.map((f) => {
          const det = el("details", { class: "faq-item" });
          const sum = el("summary", { text: f.q });
          const ans = el("p", { text: f.a });
          det.appendChild(sum);
          det.appendChild(ans);
          return det;
        })
      );
    }

    if ($("#contactOrg")) $("#contactOrg").textContent = ev.organiser;
    const mail = $("#contactEmail");
    if (mail) {
      mail.textContent = cfg.contact.email;
      mail.href = `mailto:${cfg.contact.email}`;
    }
    const tel = $("#contactPhone");
    if (tel) {
      tel.textContent = cfg.contact.phone;
      tel.href = `tel:${cfg.contact.phone.replace(/[^+\d]/g, "")}`;
    }

    const sel = $("#n_track");
    if (sel && cfg.tracks) {
      sel.replaceChildren(
        el("option", { value: "", text: "Select a track" }),
        ...cfg.tracks.map((t) => el("option", { value: t, text: t })),
        el("option", { value: NOT_SURE, text: NOT_SURE })
      );
    }

    renderNotify(cfg.registration.state);
  }

  function renderNotify(state) {
    const sec = $("#notify");
    if (!sec) return;
    if (state === "closed") {
      sec.hidden = true;
      return;
    }
    sec.hidden = false;
    if (state === "not_open") {
      $("#notifyTitle").textContent = "Get notified when registration opens";
      $("#notifyCopy").textContent = "Registration has not opened yet. Leave your details and we will email you the moment slots unlock.";
    } else {
      $("#notifyTitle").textContent = "Keep me updated with hackathon briefs";
      $("#notifyCopy").textContent = "Enter your contact details to receive workshop announcements, technical guides, and submission reminders.";
    }
  }

  function startCountdown(reg) {
    const openAt = new Date(reg.open_at).getTime();
    const deadline = new Date(reg.deadline).getTime();
    const label = $("#cdLabel");
    const wrap = $("#cdWrap");
    const closed = $("#cdClosed");
    if (!label || !wrap) return;

    function tick() {
      const now = Date.now();
      let target;
      if (now < openAt) {
        target = openAt;
        label.textContent = "Registration Opens In";
      } else if (now < deadline) {
        target = deadline;
        label.textContent = "Registration Closes In";
      } else {
        wrap.hidden = true;
        if (closed) closed.hidden = false;
        label.textContent = "Registration Closed";
        return;
      }
      wrap.hidden = false;
      if (closed) closed.hidden = true;

      const p = countdownParts(target - now);
      $("#cdD").textContent = pad(p.d);
      $("#cdH").textContent = pad(p.h);
      $("#cdM").textContent = pad(p.m);
      $("#cdS").textContent = pad(p.s);
    }

    tick();
    setInterval(tick, 1000);
  }

  function setupNotifyForm() {
    const form = $("#notifyForm");
    if (!form) return;
    const btn = $("#notifySubmit");
    const status = $("#notifyStatus");

    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      clearErrors(form);
      status.hidden = true;
      status.className = "status";
      setLoading(btn, true);

      const payload = {
        full_name: form.full_name.value.trim(),
        email: form.email.value.trim(),
        college: form.college.value.trim(),
        track_interest: form.track_interest.value,
      };

      try {
        const res = await postJSON("/api/notify-me", payload);
        status.hidden = false;
        status.classList.add("ok");
        status.textContent = res.message || "Thank you! We've saved your details.";
        form.reset();
      } catch (err) {
        if (err && err.errors) {
          showFieldErrors(form, err.errors);
        } else {
          status.hidden = false;
          status.classList.add("err");
          status.textContent = err?.message || "Could not submit form. Please check your entries.";
        }
      } finally {
        setLoading(btn, false);
      }
    });
  }

  async function init() {
    initPreloader();

    try {
      const cfg = await getJSON("/api/config");
      render(cfg);
      startCountdown(cfg.registration);
    } catch (e) {
      console.warn("Could not load initial config:", e);
    }

    setupNotifyForm();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
