document.addEventListener("DOMContentLoaded", async () => {
  if (typeof window.CHALLENGE_ID === "undefined") return;
  const toolbar = document.querySelector(".jumbotron .container .pt-3");
  if (!toolbar) return;
  const root = `${window.init.urlRoot}/admin/containers`;
  const response = await fetch(`${root}/${window.CHALLENGE_ID}/metadata`);
  if (!response.ok) return;
  const metadata = await response.json();
  const label = document.createElement("label");
  label.className = "d-block mt-3";
  const checkbox = document.createElement("input");
  checkbox.type = "checkbox";
  checkbox.checked = metadata.data.enabled;
  label.append(checkbox, " Manage with tiny-containers ");
  const link = document.createElement("a");
  link.href = `${root}?challenge=${window.CHALLENGE_ID}`;
  link.textContent = "Container settings";
  link.hidden = !checkbox.checked;
  label.append(link);
  toolbar.append(label);
  checkbox.addEventListener("change", async () => {
    const enabled = checkbox.checked;
    checkbox.disabled = true;
    try {
      const result = await fetch(`${root}/${window.CHALLENGE_ID}/eligibility`, {
        method: "POST",
        headers: {"Content-Type": "application/json", "CSRF-Token": window.init.csrfNonce},
        body: JSON.stringify({enabled}),
      });
      const body = await result.json();
      if (!body.success) throw new Error(body.error);
      link.hidden = !enabled;
    } catch (error) {
      checkbox.checked = !enabled;
      alert(error.message);
    } finally {
      checkbox.disabled = false;
    }
  });
});
