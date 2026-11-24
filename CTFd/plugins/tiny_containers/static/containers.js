(() => {
  const config = window.tinyContainers;
  const root = config.root.replace(/\/$/, "");
  const message = document.getElementById("tc-message");
  const buildPane = document.getElementById("tc-build-pane");
  const managePane = document.getElementById("tc-pane");
  const settingsPane = document.getElementById("tc-settings-pane");
  const backdrop = document.getElementById("tc-backdrop");
  const buildForm = document.getElementById("tc-build-form");
  const manageForm = document.getElementById("tc-config");
  const challengeInput = document.getElementById("tc-challenge");
  const challengeSearch = document.getElementById("tc-challenge-search");
  const challengeResults = document.getElementById("tc-challenge-results");
  const healthBody = document.getElementById("tc-health");
  const logsView = document.getElementById("tc-logs-view");
  let selectedId = null;

  document.querySelectorAll(".tc-domain-suffix").forEach(node => {
    node.textContent = `.${window.location.hostname}`;
  });

  function notice(value, error = false) {
    const active = [buildPane, managePane, settingsPane].find(pane => !pane.classList.contains("d-none"));
    const target = active?.querySelector(".tc-local-message") || message;
    target.textContent = value;
    target.className = `tc-local-message alert ${error ? "alert-danger" : "alert-success"}`;
  }

  async function request(path, data) {
    const response = await fetch(root + path, {
      method: data === undefined ? "GET" : "POST",
      headers: data === undefined ? {} : {
        "Content-Type": "application/json", "CSRF-Token": config.nonce,
      },
      body: data === undefined ? undefined : JSON.stringify(data),
      cache: "no-store",
    });
    const payload = await response.json();
    if (!response.ok || !payload.success) {
      throw new Error(payload.error || `Request failed (${response.status})`);
    }
    return payload.data;
  }

  function hidePanes() {
    for (const pane of [buildPane, managePane, settingsPane]) pane.classList.add("d-none");
    backdrop.classList.add("d-none");
    document.querySelectorAll("#tc-table tr.table-active").forEach(row => row.classList.remove("table-active"));
    document.querySelectorAll(".tc-local-message").forEach(node => {
      node.textContent = "";
      node.className = "tc-local-message alert d-none";
    });
  }

  function normalize(value) {
    return value.normalize("NFKD").toLowerCase()
      .replace(/[\u0300-\u036f]/g, "")
      .replace(/[^a-z0-9]+/g, "_").replace(/^_+|_+$/g, "");
  }

  function matchingCompose(challenge) {
    const folderName = normalize(challenge.name);
    const matches = config.files.filter(file =>
      file.split("/").slice(0, -1).some(folder => normalize(folder) === folderName)
    ).sort((a, b) => a.split("/").length - b.split("/").length);
    if (matches.length === 1) return matches[0];
    if (matches.length > 1 && matches[0].split("/").length < matches[1].split("/").length) {
      return matches[0];
    }
    return "";
  }

  function setCompose(form, file, suggest = true) {
    const picker = form.querySelector(".tc-compose-picker");
    const input = form.elements.compose_file;
    const changed = input.value !== file;
    input.value = file;
    picker.querySelector(".tc-compose-search").value = file;
    picker.querySelector(".tc-compose-results").replaceChildren();
    if (changed && suggest) suggestPort(form);
  }

  function syncProtocol(form) {
    const http = form.elements.protocol.value === "http";
    form.querySelectorAll(".tc-subdomain-group").forEach(group => {
      group.classList.toggle("d-none", !http);
    });
    const input = form.elements.subdomain;
    input.required = http;
    if (!http) {
      form.dataset.savedSubdomain = input.value;
      input.value = "";
    } else if (!input.value && form.dataset.savedSubdomain) {
      input.value = form.dataset.savedSubdomain;
    }
  }

  function chooseChallenge(challenge) {
    challengeInput.value = String(challenge.id);
    document.getElementById("tc-challenge-name").textContent =
      `${challenge.name} (${challenge.category})`;
    document.getElementById("tc-challenge-picker").classList.add("d-none");
    document.getElementById("tc-challenge-picked").classList.remove("d-none");
    document.getElementById("tc-build-details").classList.remove("d-none");
    buildForm.elements.subdomain.value = normalize(challenge.name).replace(/_/g, "-");
    setCompose(buildForm, matchingCompose(challenge));
    syncProtocol(buildForm);
  }

  function renderChallengeResults() {
    challengeResults.replaceChildren();
    const query = normalize(challengeSearch.value).replace(/_/g, "");
    const matches = config.challenges.filter(challenge =>
      normalize(`${challenge.name} ${challenge.category}`).replace(/_/g, "").includes(query)
    );
    for (const challenge of matches) {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "list-group-item list-group-item-action py-2";
      button.textContent = `${challenge.name} (${challenge.category})`;
      button.addEventListener("click", () => chooseChallenge(challenge));
      challengeResults.append(button);
    }
    if (!matches.length) {
      const empty = document.createElement("div");
      empty.className = "list-group-item text-muted py-2";
      empty.textContent = "No matching challenges";
      challengeResults.append(empty);
    }
  }

  document.querySelectorAll(".tc-compose-picker").forEach(picker => {
    const form = picker.closest("form");
    const search = picker.querySelector(".tc-compose-search");
    const results = picker.querySelector(".tc-compose-results");
    search.addEventListener("input", () => {
      if (config.files.includes(search.value)) {
        setCompose(form, search.value);
        return;
      }
      form.elements.compose_file.value = "";
      results.replaceChildren();
      const query = normalize(search.value).replace(/_/g, "");
      if (!query) return;
      const matches = config.files.filter(file =>
        normalize(file).replace(/_/g, "").includes(query)
      ).slice(0, 6);
      for (const file of matches) {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "list-group-item list-group-item-action py-2 text-left";
        button.textContent = file;
        button.addEventListener("click", () => setCompose(form, file));
        results.append(button);
      }
      if (!matches.length) {
        const empty = document.createElement("div");
        empty.className = "list-group-item text-muted py-2";
        empty.textContent = "No matching Compose files";
        results.append(empty);
      }
    });
    search.addEventListener("focus", () => {
      if (search.value) search.dispatchEvent(new Event("input"));
    });
    search.addEventListener("keydown", event => {
      if (event.key === "Enter" && results.querySelector("button")) {
        event.preventDefault();
        results.querySelector("button").click();
      }
    });
  });

  async function suggestPort(form) {
    const file = form.elements.compose_file.value;
    form.elements.port.value = "";
    if (!file) return;
    try {
      const target = await request(`/target?file=${encodeURIComponent(file)}`);
      if (form.elements.compose_file.value === file && !form.elements.port.value) {
        form.elements.port.value = target.port || "";
      }
    } catch (error) {
      notice(error.message, true);
    }
  }

  function renderHealth(services) {
    healthBody.replaceChildren();
    if (!services.length) {
      const row = healthBody.insertRow();
      const cell = row.insertCell();
      cell.colSpan = 4;
      cell.className = "text-muted";
      cell.textContent = "No containers running";
      return;
    }
    for (const service of services) {
      const row = healthBody.insertRow();
      const health = service.health === "none" ? "No healthcheck" : service.health;
      for (const value of [service.name, service.container, service.state, health]) {
        row.insertCell().textContent = value || "—";
      }
    }
  }

  function renderManaged(record) {
    document.getElementById("tc-detail-status").textContent = record.status;
    document.getElementById("tc-endpoint").textContent = record.endpoint || "Not published";
    document.getElementById("tc-deployment-summary").textContent =
      `${record.compose_file} · ${record.protocol.toUpperCase()} · port ${record.host_port}`;
    const unavailable = record.status === "unavailable";
    const launch = document.querySelector('[data-action="launch"]');
    const restart = document.querySelector('[data-action="restart"]');
    const stop = document.querySelector('[data-action="stop"]');
    launch.classList.toggle("d-none", record.running);
    restart.classList.toggle("d-none", !record.running);
    stop.classList.toggle("d-none", !record.services.length);
    launch.disabled = unavailable;
    restart.disabled = unavailable;
    stop.disabled = unavailable;
    document.getElementById("tc-visible").checked = record.visible;
    renderHealth(record.services);
  }

  function renderRowActions(row, record) {
    row.querySelector('[data-row-action="launch"]').classList.toggle("d-none", record.running);
    row.querySelector('[data-row-action="restart"]').classList.toggle("d-none", !record.running);
    row.querySelector('[data-row-action="stop"]').classList.toggle("d-none", !record.running);
    row.querySelectorAll("[data-row-action]").forEach(button => {
      button.disabled = record.status === "unavailable";
    });
  }

  async function runAction(id, action, button) {
    button.disabled = true;
    try {
      await request(`/${id}/action`, {action});
      location.reload();
    } catch (error) {
      notice(error.message, true);
      button.disabled = false;
    }
  }

  function setEditMode(enabled) {
    manageForm.classList.toggle("d-none", !enabled);
    document.getElementById("tc-deployment-summary").classList.toggle("d-none", enabled);
    document.getElementById("tc-remove").classList.toggle("d-none", !enabled);
    const button = document.getElementById("tc-edit-deployment");
    button.setAttribute("aria-expanded", String(enabled));
    button.innerHTML = enabled
      ? '<i class="fas fa-save" aria-hidden="true"></i> <span>Save</span>'
      : '<i class="fas fa-edit" aria-hidden="true"></i> <span>Edit</span>';
  }

  function openManaged(id) {
    const record = config.records[id];
    if (!record) return;
    selectedId = id;
    hidePanes();
    managePane.classList.remove("d-none");
    backdrop.classList.remove("d-none");
    document.querySelector(`#tc-table tr[data-id="${id}"]`)?.classList.add("table-active");
    document.getElementById("tc-title").textContent = record.name;
    setEditMode(false);
    setCompose(manageForm, record.compose_file, false);
    manageForm.elements.port.value = record.host_port;
    manageForm.elements.subdomain.value = record.subdomain || "";
    manageForm.elements.protocol.value = record.protocol;
    syncProtocol(manageForm);
    renderManaged(record);
    location.hash = `container-${id}`;
  }

  function openBuild(id) {
    selectedId = null;
    hidePanes();
    buildPane.classList.remove("d-none");
    backdrop.classList.remove("d-none");
    buildForm.reset();
    challengeInput.value = "";
    challengeSearch.value = "";
    challengeResults.replaceChildren();
    document.getElementById("tc-challenge-picker").classList.remove("d-none");
    document.getElementById("tc-challenge-picked").classList.add("d-none");
    document.getElementById("tc-build-details").classList.add("d-none");
    setCompose(buildForm, "", false);
    const challenge = config.challenges.find(item => item.id === id);
    if (challenge) chooseChallenge(challenge);
    else {
      challengeSearch.focus();
      renderChallengeResults();
    }
    location.hash = "";
  }

  document.querySelectorAll("#tc-table tbody tr[data-id]").forEach(row => {
    row.addEventListener("click", () => openManaged(Number(row.dataset.id)));
    row.addEventListener("keydown", event => {
      if (event.key === "Enter" && event.target === row) openManaged(Number(row.dataset.id));
    });
    row.querySelectorAll("[data-row-action]").forEach(button => {
      button.addEventListener("click", event => {
        event.stopPropagation();
        runAction(Number(row.dataset.id), button.dataset.rowAction, button);
      });
    });
  });
  document.querySelectorAll("[data-close-pane]").forEach(button => {
    button.addEventListener("click", () => { hidePanes(); location.hash = ""; });
  });
  backdrop.addEventListener("click", () => { hidePanes(); location.hash = ""; });
  document.getElementById("tc-add").addEventListener("click", () => openBuild());
  document.getElementById("tc-settings").addEventListener("click", () => {
    const opening = settingsPane.classList.contains("d-none");
    hidePanes();
    if (opening) {
      settingsPane.classList.remove("d-none");
      backdrop.classList.remove("d-none");
      location.hash = "";
    }
  });
  challengeSearch.addEventListener("input", renderChallengeResults);
  challengeSearch.addEventListener("focus", renderChallengeResults);
  challengeSearch.addEventListener("keydown", event => {
    if (event.key === "Enter" && challengeResults.querySelector("button")) {
      event.preventDefault();
      challengeResults.querySelector("button").click();
    }
  });
  document.getElementById("tc-change-challenge").addEventListener("click", () => openBuild());
  document.getElementById("tc-edit-deployment").addEventListener("click", () => {
    if (manageForm.classList.contains("d-none")) setEditMode(true);
    else if (!manageForm.elements.compose_file.value) notice("Select a Compose file", true);
    else manageForm.requestSubmit();
  });
  for (const form of [buildForm, manageForm]) {
    form.elements.protocol.addEventListener("change", () => syncProtocol(form));
  }

  function deployment(form) {
    return {
      enabled: true,
      compose_file: form.elements.compose_file.value,
      port: Number(form.elements.port.value),
      subdomain: form.elements.protocol.value === "http" ? form.elements.subdomain.value : null,
      protocol: form.elements.protocol.value,
    };
  }

  buildForm.addEventListener("submit", async event => {
    event.preventDefault();
    const id = Number(challengeInput.value);
    if (!id || !buildForm.elements.compose_file.value) {
      notice("Choose a challenge and Compose file", true);
      return;
    }
    const button = buildForm.querySelector('button[type="submit"]');
    button.disabled = true;
    try {
      await request(`/${id}/configure`, deployment(buildForm));
      await request(`/${id}/action`, {action: "build"});
      location.hash = `container-${id}`;
      location.reload();
    } catch (error) {
      notice(error.message, true);
      button.disabled = false;
    }
  });
  manageForm.addEventListener("submit", async event => {
    event.preventDefault();
    try {
      await request(`/${selectedId}/configure`, deployment(manageForm));
      location.reload();
    } catch (error) { notice(error.message, true); }
  });
  managePane.querySelectorAll("[data-action]").forEach(button => {
    button.addEventListener("click", () => runAction(selectedId, button.dataset.action, button));
  });
  document.getElementById("tc-visible").addEventListener("change", async event => {
    try {
      await request(`/${selectedId}/action`, {action: "visibility"});
      config.records[selectedId].visible = event.target.checked;
      document.querySelector(`#tc-table tr[data-id="${selectedId}"] [data-field="visible"]`)
        .textContent = event.target.checked ? "Visible" : "Hidden";
    } catch (error) {
      event.target.checked = !event.target.checked;
      notice(error.message, true);
    }
  });
  document.getElementById("tc-remove").addEventListener("click", async () => {
    try {
      await request(`/${selectedId}/configure`, {enabled: false});
      location.href = root;
    } catch (error) { notice(error.message, true); }
  });
  document.getElementById("tc-open-logs").addEventListener("click", async () => {
    logsView.classList.remove("d-none");
    document.getElementById("tc-logs").textContent = "Loading logs…";
    try {
      document.getElementById("tc-logs").textContent = await request(`/${selectedId}/logs`) || "No logs";
    } catch (error) {
      document.getElementById("tc-logs").textContent = error.message;
    }
  });
  document.getElementById("tc-close-logs").addEventListener("click", () => {
    logsView.classList.add("d-none");
    document.getElementById("tc-logs").textContent = "";
  });
  document.getElementById("tc-settings-form").addEventListener("submit", async event => {
    event.preventDefault();
    try {
      await request("/settings", {grace_minutes: Number(event.target.elements.grace_minutes.value)});
      location.reload();
    } catch (error) { notice(error.message, true); }
  });

  async function refresh() {
    try {
      const rows = await request("/status");
      for (const row of rows) {
        const element = document.querySelector(`#tc-table tr[data-id="${row.id}"]`);
        if (!element) continue;
        for (const field of ["status", "cpu", "memory"]) {
          element.querySelector(`[data-field="${field}"]`).textContent = row[field];
        }
        element.querySelector('[data-field="visible"]').textContent = row.visible ? "Visible" : "Hidden";
        Object.assign(config.records[row.id], row);
        renderRowActions(element, config.records[row.id]);
        if (selectedId === row.id) renderManaged(config.records[row.id]);
      }
    } catch (error) { notice(error.message, true); }
  }
  setInterval(refresh, 5000);
  const hash = location.hash.match(/^#container-(\d+)$/);
  if (hash && config.records[Number(hash[1])]) openManaged(Number(hash[1]));
  else if (config.requestedChallenge) {
    if (config.records[config.requestedChallenge]) openManaged(config.requestedChallenge);
    else openBuild(config.requestedChallenge);
  }
})();
