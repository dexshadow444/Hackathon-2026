(() => {
  const {
    $,
    $$,
    el,
    fmt,
    DATETIME,
    getJSON,
    postJSON,
    setLoading,
    clearErrors,
    showFieldErrors,
    setupModal,
  } = HK;

  let currentStep = 1;
  let selectedFile = null;
  let pendingOrderData = null;

  const MIN_CREW = 3; // + 1 leader = 4
  const MAX_CREW = 5; // + 1 leader = 6
  let crewList = [];

  // Terms modal setup
  const termsModal = setupModal("termsModal");
  const sandboxModal = setupModal("sandboxModal");

  // DOM Elements
  const gateCard = $("#gateCard");
  const wizardRoot = $("#wizardRoot");
  const form = $("#wizardForm");
  const crewContainer = $("#crewMembersContainer");
  const liveTeamCount = $("#liveTeamCount");
  const btnAddMember = $("#btnAddMember");
  const maxCapacityMsg = $("#maxCapacityMsg");
  const termsCheckbox = $("#w_terms_accepted");
  const btnSubmitPayment = $("#btnSubmitPayment");

  // Step sections
  const stepSection1 = $("#stepSection1");
  const stepSection2 = $("#stepSection2");
  const stepSection3 = $("#stepSection3");
  const stepNode1 = $("#stepNode1");
  const stepNode2 = $("#stepNode2");
  const stepNode3 = $("#stepNode3");

  // ---------------- Initialize & Gate Check ----------------
  async function init() {
    try {
      const reg = await getJSON("/api/registration-status");
      if (reg.state === "not_open") {
        gateCard.replaceChildren(
          el("h3", { text: "Registration Has Not Opened Yet" }),
          el("p", { class: "muted", text: `Registration will open on ${fmt(reg.open_at, DATETIME)} (IST). Please return then or leave your email on the event homepage.` }),
          el("a", { class: "btn btn-outline", href: "/", text: "← Back to Event Page" })
        );
        return;
      }
      if (reg.state === "closed") {
        gateCard.replaceChildren(
          el("h3", { text: "Registration is Closed" }),
          el("p", { class: "muted", text: `The registration deadline was ${fmt(reg.deadline, DATETIME)} (IST). Thank you for your interest.` }),
          el("a", { class: "btn btn-outline", href: "/", text: "← Back to Event Page" })
        );
        return;
      }

      // Open: reveal wizard and setup crew
      gateCard.hidden = true;
      wizardRoot.hidden = false;
      setupInitialCrew();
      setupEvents();
    } catch (e) {
      gateCard.replaceChildren(
        el("h3", { text: "Service Unavailable" }),
        el("p", { class: "muted", text: "Could not verify registration window. Please check your connection and reload." }),
        el("button", { class: "btn btn-primary btn-sm", text: "Retry", onclick: () => location.reload() })
      );
    }
  }

  // ---------------- Crew Members Setup ----------------
  function setupInitialCrew() {
    crewContainer.replaceChildren();
    crewList = [];
    for (let i = 1; i <= MIN_CREW; i++) {
      addCrewCard(i, false);
    }
    updateCapacityUI();
  }

  function addCrewCard(memberNum, isOptional = false) {
    const cardId = `crew-member-${Date.now()}-${Math.random().toString(36).substr(2, 4)}`;
    const card = el("div", { class: "crew-member-card", id: cardId });

    const head = el("div", { class: "crew-card-head" });
    const badge = el("span", {
      class: "crew-badge",
      text: `Crew Member #${memberNum} ${isOptional ? "(Optional)" : "(Required)"}`,
    });
    head.appendChild(badge);

    if (isOptional) {
      const removeBtn = el("button", {
        type: "button",
        class: "btn-remove-member",
        text: "Remove Member",
        onclick: () => removeCrewCard(cardId),
      });
      head.appendChild(removeBtn);
    }
    card.appendChild(head);

    const grid1 = el("div", { class: "form-grid" });
    grid1.innerHTML = `
      <div class="field">
        <label>Member Full Name *</label>
        <input type="text" class="c-name" placeholder="Full name" required maxlength="128">
        <span class="field-error err-c-name"></span>
      </div>
      <div class="field">
        <label>Mobile Number * <small>(10-digit Indian, starting 6–9)</small></label>
        <input type="tel" class="c-phone" placeholder="9876543210" required maxlength="10">
        <span class="field-error err-c-phone"></span>
      </div>
    `;
    card.appendChild(grid1);

    const grid2 = el("div", { class: "form-grid", style: "grid-template-columns: 1fr 1fr 1fr;" });
    grid2.innerHTML = `
      <div class="field">
        <label>Email Address *</label>
        <input type="email" class="c-email" placeholder="student@college.edu" required>
        <span class="field-error err-c-email"></span>
      </div>
      <div class="field">
        <label>Department <small>(Optional)</small></label>
        <input type="text" class="c-dept" placeholder="e.g. Electrical">
      </div>
      <div class="field">
        <label>Year of Study</label>
        <select class="c-year">
          <option value="1st Year">1st Year</option>
          <option value="2nd Year">2nd Year</option>
          <option value="3rd Year" selected>3rd Year</option>
          <option value="4th Year">4th Year</option>
          <option value="Postgraduate">Postgraduate</option>
        </select>
      </div>
    `;
    card.appendChild(grid2);

    crewContainer.appendChild(card);
    crewList.push(cardId);
    updateCapacityUI();
  }

  function removeCrewCard(cardId) {
    if (crewList.length <= MIN_CREW) return;
    const card = document.getElementById(cardId);
    if (card) {
      card.remove();
      crewList = crewList.filter((id) => id !== cardId);
      reindexCrewCards();
      updateCapacityUI();
    }
  }

  function reindexCrewCards() {
    const cards = crewContainer.querySelectorAll(".crew-member-card");
    cards.forEach((c, idx) => {
      const num = idx + 1;
      const isOpt = num > MIN_CREW;
      const badge = c.querySelector(".crew-badge");
      if (badge) {
        badge.textContent = `Crew Member #${num} ${isOpt ? "(Optional)" : "(Required)"}`;
      }
    });
  }

  function updateCapacityUI() {
    const totalTeam = crewList.length + 1; // + 1 for Leader
    liveTeamCount.textContent = `${totalTeam} / 6`;

    if (crewList.length >= MAX_CREW) {
      btnAddMember.disabled = true;
      maxCapacityMsg.hidden = false;
    } else {
      btnAddMember.disabled = false;
      maxCapacityMsg.hidden = true;
    }
  }

  // ---------------- Step Transitions & Navigation ----------------
  function goToStep(step) {
    currentStep = step;
    stepSection1.hidden = step !== 1;
    stepSection2.hidden = step !== 2;
    stepSection3.hidden = step !== 3;

    stepNode1.classList.toggle("active", step === 1);
    stepNode1.classList.toggle("completed", step > 1);
    stepNode2.classList.toggle("active", step === 2);
    stepNode2.classList.toggle("completed", step > 2);
    stepNode3.classList.toggle("active", step === 3);

    window.scrollTo({ top: wizardRoot.offsetTop - 80, behavior: "smooth" });
  }

  // ---------------- Validation ----------------
  const INDIAN_MOBILE = /^[6-9]\d{9}$/;

  function validateStep1() {
    clearErrors(form);
    let valid = true;

    // Team name
    const teamName = form.team_name.value.trim();
    if (!teamName) {
      showError("team_name", "Team name is required.");
      valid = false;
    } else if (teamName.length > 128) {
      showError("team_name", "Maximum 128 characters allowed.");
      valid = false;
    }

    // College
    const college = form.college_name.value.trim();
    if (!college) {
      showError("college_name", "College or Institution name is required.");
      valid = false;
    }

    // Track
    const track = form.track.value;
    if (!track) {
      showError("track", "Please choose a track.");
      valid = false;
    }

    // Leader
    const leaderName = form.leader_name.value.trim();
    if (!leaderName) {
      showError("leader_name", "Team Leader name is required.");
      valid = false;
    }

    const leaderPhone = form.leader_phone.value.trim();
    if (!INDIAN_MOBILE.test(leaderPhone)) {
      showError("leader_phone", "Enter a valid 10-digit Indian mobile number starting 6–9.");
      valid = false;
    }

    const leaderEmail = form.leader_email.value.trim();
    if (!leaderEmail || !leaderEmail.includes("@") || !leaderEmail.includes(".")) {
      showError("leader_email", "Enter a valid email address.");
      valid = false;
    }

    const leaderDept = form.leader_department.value.trim();
    if (!leaderDept) {
      showError("leader_department", "Leader department is required.");
      valid = false;
    }

    const leaderYear = form.leader_year.value;
    if (!leaderYear) {
      showError("leader_year", "Select leader year of study.");
      valid = false;
    }

    // Crew members
    const cards = crewContainer.querySelectorAll(".crew-member-card");
    cards.forEach((card, idx) => {
      const name = card.querySelector(".c-name").value.trim();
      const phone = card.querySelector(".c-phone").value.trim();
      const email = card.querySelector(".c-email").value.trim();

      if (!name) {
        card.querySelector(".err-c-name").textContent = `Member #${idx + 1} name is required.`;
        valid = false;
      } else {
        card.querySelector(".err-c-name").textContent = "";
      }

      if (!INDIAN_MOBILE.test(phone)) {
        card.querySelector(".err-c-phone").textContent = "Must be a 10-digit number starting 6–9.";
        valid = false;
      } else {
        card.querySelector(".err-c-phone").textContent = "";
      }

      if (!email || !email.includes("@") || !email.includes(".")) {
        card.querySelector(".err-c-email").textContent = "Enter a valid email.";
        valid = false;
      } else {
        card.querySelector(".err-c-email").textContent = "";
      }
    });

    return valid;
  }

  function validateStep2() {
    clearErrors(form);
    let valid = true;

    const title = form.idea_title.value.trim();
    if (!title) {
      showError("idea_title", "Idea title is required.");
      valid = false;
    } else if (title.length > 100) {
      showError("idea_title", "Title cannot exceed 100 characters.");
      valid = false;
    }

    const summary = form.idea_summary.value.trim();
    if (!summary) {
      showError("idea_summary", "Abstract / Summary is required.");
      valid = false;
    } else if (summary.length > 10000) {
      showError("idea_summary", "Abstract cannot exceed 10,000 characters.");
      valid = false;
    }

    const desc = form.idea_description.value.trim();
    if (!desc) {
      showError("idea_description", "Technical description is required.");
      valid = false;
    } else if (desc.length > 50000) {
      showError("idea_description", "Description cannot exceed 50,000 characters.");
      valid = false;
    }

    if (!selectedFile) {
      showError("idea_presentation", "Please upload your presentation file (.pptx, .ppt, or .pdf).");
      valid = false;
    }

    return valid;
  }

  function showError(fieldName, msg) {
    const err = $(`#err-${fieldName}`);
    if (err) {
      err.textContent = msg;
      err.closest(".field")?.classList.add("has-error");
    }
  }

  // ---------------- Populate Step 3 Review ----------------
  function populateReview() {
    $("#revTeamName").textContent = form.team_name.value.trim();
    $("#revCollege").textContent = form.college_name.value.trim();
    $("#revTrack").textContent = form.track.value;

    $("#revLeaderName").textContent = form.leader_name.value.trim();
    $("#revLeaderPhone").textContent = form.leader_phone.value.trim();
    $("#revLeaderEmail").textContent = form.leader_email.value.trim();
    $("#revLeaderDeptYear").textContent = `${form.leader_department.value.trim()} · ${form.leader_year.value}`;

    // Crew members
    const crewDiv = $("#revCrewList");
    crewDiv.replaceChildren();
    const cards = crewContainer.querySelectorAll(".crew-member-card");
    $("#revCrewCount").textContent = cards.length;

    cards.forEach((c, idx) => {
      const name = c.querySelector(".c-name").value.trim();
      const phone = c.querySelector(".c-phone").value.trim();
      const email = c.querySelector(".c-email").value.trim();
      const dept = c.querySelector(".c-dept").value.trim();
      const year = c.querySelector(".c-year").value;

      const item = el("div", {
        style: "display:flex; justify-content:space-between; padding:0.4rem 0; border-bottom:1px solid var(--border-light); font-size:0.92rem;",
      });
      item.innerHTML = `
        <div><strong>#${idx + 1} ${name}</strong> <span class="muted">(${dept || "General"} · ${year})</span></div>
        <div class="mono" style="color:var(--text-muted);">${phone} · ${email}</div>
      `;
      crewDiv.appendChild(item);
    });

    $("#revIdeaTitle").textContent = form.idea_title.value.trim();
    const sum = form.idea_summary.value.trim();
    $("#revIdeaSummary").textContent = sum.length > 250 ? sum.substring(0, 250) + "..." : sum;
    $("#revFileName").textContent = selectedFile ? `${selectedFile.name} (${(selectedFile.size / (1024 * 1024)).toFixed(2)} MB)` : "None";
  }

  // ---------------- Event Listeners ----------------
  function setupEvents() {
    // Team name live check debounce
    let teamNameTimer = null;
    const teamInput = $("#w_team_name");
    const teamHint = $("#hint-team_name");

    teamInput.addEventListener("input", () => {
      clearTimeout(teamNameTimer);
      const val = teamInput.value.trim();
      if (!val) {
        teamHint.className = "field-hint";
        teamHint.textContent = "Unique, case-insensitive team identity.";
        return;
      }
      teamNameTimer = setTimeout(async () => {
        try {
          const res = await getJSON(`/api/check-team-name?name=${encodeURIComponent(val)}`);
          if (res.available) {
            teamHint.className = "field-hint ok";
            teamHint.textContent = "✓ Team name is available!";
            $(`#err-team_name`).textContent = "";
            teamInput.closest(".field")?.classList.remove("has-error");
          } else {
            teamHint.className = "field-hint";
            showError("team_name", res.message);
          }
        } catch {}
      }, 350);
    });

    // Add member
    btnAddMember.addEventListener("click", () => {
      if (crewList.length < MAX_CREW) {
        addCrewCard(crewList.length + 1, true);
      }
    });

    // Step 1 -> Step 2
    $("#btnNextStep1").addEventListener("click", () => {
      if (validateStep1()) {
        goToStep(2);
      }
    });

    // Step 2 -> Step 1
    $("#btnBackToStep1").addEventListener("click", () => goToStep(1));
    $("#btnBackToStep1_bottom").addEventListener("click", () => goToStep(1));

    // Character counters
    setupCharCounter("w_idea_title", "cc_idea_title", 100);
    setupCharCounter("w_idea_summary", "cc_idea_summary", 10000);
    setupCharCounter("w_idea_desc", "cc_idea_desc", 50000);

    // File upload
    setupFileUpload();

    // Step 2 -> Step 3
    $("#btnNextStep2").addEventListener("click", () => {
      if (validateStep2()) {
        populateReview();
        goToStep(3);
      }
    });

    // Step 3 -> Step 2
    $("#btnBackToStep2").addEventListener("click", () => goToStep(2));
    $("#btnBackToStep2_bottom").addEventListener("click", () => goToStep(2));

    // Jump edit links
    $("#editLinkTeam").addEventListener("click", () => goToStep(1));
    $("#editLinkLeader").addEventListener("click", () => goToStep(1));
    $("#editLinkCrew").addEventListener("click", () => goToStep(1));
    $("#editLinkIdea").addEventListener("click", () => goToStep(2));

    // Terms modal
    $("#btnOpenTermsModal").addEventListener("click", (e) => {
      e.preventDefault();
      termsModal.open();
    });

    // Terms checkbox toggle
    termsCheckbox.addEventListener("change", () => {
      btnSubmitPayment.disabled = !termsCheckbox.checked;
      if (termsCheckbox.checked) {
        $(`#err-terms_accepted`).textContent = "";
      }
    });

    // Final Form Submission
    form.addEventListener("submit", handleRegistrationSubmit);
  }

  function setupCharCounter(inputId, counterId, maxLen) {
    const input = $(`#${inputId}`);
    const counter = $(`#${counterId}`);
    if (!input || !counter) return;

    input.addEventListener("input", () => {
      const len = input.value.length;
      counter.textContent = `${len.toLocaleString("en-IN")} / ${maxLen.toLocaleString("en-IN")}`;
      counter.classList.toggle("warning", len > maxLen * 0.95);
    });
  }

  function setupFileUpload() {
    const dropzone = $("#dropzone");
    const fileInput = $("#w_idea_file");
    const btnBrowse = $("#btnBrowseFile");
    const box = $("#fileSelectedBox");
    const fileNameEl = $("#selectedFileName");
    const fileSizeEl = $("#selectedFileSize");
    const btnRemove = $("#btnRemoveFile");

    btnBrowse.addEventListener("click", (e) => {
      e.preventDefault();
      e.stopPropagation();
      fileInput.click();
    });

    dropzone.addEventListener("click", () => fileInput.click());

    dropzone.addEventListener("dragover", (e) => {
      e.preventDefault();
      dropzone.classList.add("dragover");
    });
    dropzone.addEventListener("dragleave", () => dropzone.classList.remove("dragover"));
    dropzone.addEventListener("drop", (e) => {
      e.preventDefault();
      dropzone.classList.remove("dragover");
      if (e.dataTransfer.files && e.dataTransfer.files[0]) {
        handleFileSelect(e.dataTransfer.files[0]);
      }
    });

    fileInput.addEventListener("change", () => {
      if (fileInput.files && fileInput.files[0]) {
        handleFileSelect(fileInput.files[0]);
      }
    });

    btnRemove.addEventListener("click", () => {
      selectedFile = null;
      fileInput.value = "";
      box.hidden = true;
      dropzone.hidden = false;
    });

    function handleFileSelect(file) {
      const ext = "." + file.name.split(".").pop().toLowerCase();
      if (![".pptx", ".ppt", ".pdf"].includes(ext)) {
        showError("idea_presentation", `Invalid file type '${ext}'. Please choose a .pptx, .ppt, or .pdf file.`);
        return;
      }
      if (file.size > 10 * 1024 * 1024) {
        showError("idea_presentation", `File is ${(file.size / (1024 * 1024)).toFixed(1)} MB. Maximum allowed size is 10 MB.`);
        return;
      }

      selectedFile = file;
      $(`#err-idea_presentation`).textContent = "";
      fileNameEl.textContent = file.name;
      fileSizeEl.textContent = `${(file.size / (1024 * 1024)).toFixed(2)} MB`;
      dropzone.hidden = true;
      box.hidden = false;
    }
  }

  // ---------------- Payment and Submission ----------------
  async function handleRegistrationSubmit(e) {
    e.preventDefault();
    if (!termsCheckbox.checked) {
      showError("terms_accepted", "You must accept the Terms & Conditions to proceed.");
      return;
    }

    setLoading(btnSubmitPayment, true);

    // Build Crew array
    const membersData = [];
    crewContainer.querySelectorAll(".crew-member-card").forEach((c) => {
      membersData.push({
        name: c.querySelector(".c-name").value.trim(),
        mobile: c.querySelector(".c-phone").value.trim(),
        email: c.querySelector(".c-email").value.trim(),
        department: c.querySelector(".c-dept").value.trim(),
        year: c.querySelector(".c-year").value,
      });
    });

    const fd = new FormData();
    fd.append("team_name", form.team_name.value.trim());
    fd.append("college_name", form.college_name.value.trim());
    fd.append("track", form.track.value);
    fd.append("leader_name", form.leader_name.value.trim());
    fd.append("leader_phone", form.leader_phone.value.trim());
    fd.append("leader_email", form.leader_email.value.trim());
    fd.append("leader_department", form.leader_department.value.trim());
    fd.append("leader_year", form.leader_year.value);
    fd.append("leader_gender", form.leader_gender.value || "");
    fd.append("leader_id_number", form.leader_id_number.value || "");
    fd.append("members_data", JSON.stringify(membersData));
    fd.append("idea_title", form.idea_title.value.trim());
    fd.append("idea_summary", form.idea_summary.value.trim());
    fd.append("idea_description", form.idea_description.value.trim());
    fd.append("idea_presentation", selectedFile);
    fd.append("terms_accepted", "true");

    try {
      const res = await fetch("/api/register", {
        method: "POST",
        headers: { Accept: "application/json" },
        body: fd,
      });
      const data = await res.json();

      if (!res.ok) {
        if (data.errors) {
          showFieldErrors(form, data.errors);
          // If error is in Step 1 or 2, jump there
          if (Object.keys(data.errors).some((k) => k.startsWith("team") || k.startsWith("leader") || k.startsWith("member"))) {
            goToStep(1);
          } else if (Object.keys(data.errors).some((k) => k.startsWith("idea"))) {
            goToStep(2);
          }
        } else {
          alert(data.message || "Registration failed. Please check your entries.");
        }
        setLoading(btnSubmitPayment, false);
        return;
      }

      // Registration pending saved, proceed to payment
      pendingOrderData = data;
      triggerPaymentFlow(data);
    } catch (err) {
      alert("Network error occurred during registration. Please try again.");
      setLoading(btnSubmitPayment, false);
    }
  }

  function triggerPaymentFlow(data) {
    const order = data.order;

    // Check if Sandbox Simulator
    if (order.is_sandbox) {
      $("#sbxOrderId").textContent = order.order_id;
      sandboxModal.open();

      $("#btnSimulateSuccess").onclick = async () => {
        sandboxModal.close();
        await completePaymentVerification({
          razorpay_order_id: order.order_id,
          razorpay_payment_id: `pay_sbx_${Date.now()}`,
          razorpay_signature: `sig_sbx_mock_valid`,
        });
      };

      $("#btnSimulateFail").onclick = () => {
        sandboxModal.close();
        setLoading(btnSubmitPayment, false);
        alert("Payment was cancelled or failed. Your registration details remain saved. You can retry anytime.");
      };
      return;
    }

    // Live / Test Razorpay Modal
    const options = {
      key: order.key_id,
      amount: order.amount,
      currency: order.currency,
      name: "JM Vertex Hackathon 2027",
      description: `Team Registration: ${data.team_name}`,
      order_id: order.order_id,
      prefill: {
        name: data.leader_name,
        email: data.leader_email,
        contact: data.leader_phone,
      },
      theme: { color: "#147A47" },
      handler: async function (response) {
        await completePaymentVerification({
          razorpay_order_id: response.razorpay_order_id,
          razorpay_payment_id: response.razorpay_payment_id,
          razorpay_signature: response.razorpay_signature,
        });
      },
      modal: {
        ondismiss: function () {
          setLoading(btnSubmitPayment, false);
          alert("Payment window closed. Your registration details are saved in pending status. You may retry payment.");
        },
      },
    };

    const rzp = new window.Razorpay(options);
    rzp.open();
  }

  async function completePaymentVerification(paymentPayload) {
    try {
      const verifyRes = await postJSON("/api/payment/verify", paymentPayload);
      if (verifyRes.ok && verifyRes.redirect_url) {
        window.location.href = verifyRes.redirect_url;
      } else {
        alert("Payment verification could not be confirmed. Please contact hackathon organizers with your payment ID.");
        setLoading(btnSubmitPayment, false);
      }
    } catch (e) {
      alert("Payment verification error: " + (e.message || "Please contact support."));
      setLoading(btnSubmitPayment, false);
    }
  }

  // Run on page load
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
