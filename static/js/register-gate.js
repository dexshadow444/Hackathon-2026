(() => {
  const { $, el, fmt, DATETIME, getJSON } = HK;
  const gate = $("#gate");

  function message(title, text, extra) {
    gate.replaceChildren(el("h1", { text: title, style: "font-size:1.8rem" }), el("p", { class: "muted", text }), ...(extra || []));
  }

  async function init() {
    let reg;
    try { reg = await getJSON("/api/registration-status"); }
    catch { return message("Something went wrong", "We could not check registration status. Please refresh the page."); }

    const home = el("a", { class: "btn btn-outline", href: "/", text: "Back to event page" });
    if (reg.state === "not_open") {
      message("Registration has not opened yet", `Registration opens on ${fmt(reg.open_at, DATETIME)} (IST). Leave your email on the event page and we will notify you.`, [home]);
    } else if (reg.state === "closed") {
      message("Registration is closed", `The deadline was ${fmt(reg.deadline, DATETIME)} (IST). Thank you for your interest.`, [home]);
    } else {
      // Registration is open. The wizard (Day 2) replaces this placeholder.
      gate.hidden = true;
      $("#wizardRoot").hidden = false;
      $("#wizardRoot").append(el("div", { class: "gate-card" }, el("h1", { text: "Registration is open", style: "font-size:1.8rem" }), el("p", { class: "muted", text: "The registration form is being built (Day 2)." })));
    }
  }
  init();
})();
