(function () {
  const search = document.getElementById("sheet-q");
  const visible = document.getElementById("visible-count");
  if (!document.querySelector(".sheet")) return;

  const filter = () => {
    if (!search) return;
    const q = search.value.trim().toLowerCase();
    let shown = 0;
    document.querySelectorAll("tr.svc-row:not(.row-new)").forEach((row) => {
      const hay = row.getAttribute("data-search") || "";
      const on = !q || hay.includes(q);
      row.hidden = !on;
      if (on) shown += 1;
    });
    if (visible) visible.textContent = String(shown);
  };
  if (search) search.addEventListener("input", filter);

  const flash = (row, text, ok) => {
    const msg = row.querySelector(".row-msg");
    if (!msg) return;
    msg.textContent = text || "";
    msg.classList.toggle("ok", Boolean(ok));
    msg.classList.toggle("err", !ok && Boolean(text));
  };

  const markDirty = (event) => {
    const row = event.target.closest && event.target.closest("tr.svc-row");
    if (row && !row.classList.contains("row-new")) row.classList.add("dirty");
  };
  document.addEventListener("input", markDirty);
  document.addEventListener("change", markDirty);

  document.addEventListener("submit", async (event) => {
    const form = event.target;
    if (!(form instanceof HTMLFormElement)) return;
    const isCreate = form.classList.contains("svc-form") && /\/services\/new\/?$/.test(form.action);
    const isSave = form.classList.contains("svc-form") && !isCreate;
    const isDelete = form.classList.contains("del-form");
    if (!isSave && !isDelete) return;
    event.preventDefault();
    const row = form.closest("tr.svc-row");
    if (!row) return;

    if (isDelete) {
      const name = row.querySelector(".del-btn")?.getAttribute("data-name") || "המענה";
      if (!window.confirm(`למחוק את «${name}» ואת כל הפרטים שלו? הפעולה לא ניתנת לביטול.`)) return;
    }

    try {
      const response = await fetch(form.action, {
        method: "POST",
        body: new FormData(form),
        headers: { "X-Requested-With": "fetch" },
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok || data.ok === false) {
        flash(row, data.error || "השמירה נכשלה.", false);
        return;
      }
      if (isDelete) {
        row.remove();
        filter();
        return;
      }
      row.classList.remove("dirty");
      row.classList.add("saved");
      flash(row, data.notice || "נשמר", true);
      const updated = row.querySelector('[data-key="last_updated"]');
      if (updated && data.last_updated) updated.textContent = data.last_updated;
      const nameInput = row.querySelector(".name-input");
      const cityInput = row.querySelector('input[name="city"]');
      const phoneInput = row.querySelector('input[name="phone"]');
      const addressInput = row.querySelector('input[name="address"]');
      row.setAttribute(
        "data-search",
        [nameInput && nameInput.value, cityInput && cityInput.value, phoneInput && phoneInput.value, addressInput && addressInput.value]
          .filter(Boolean)
          .join(" ")
          .toLowerCase()
      );
      window.setTimeout(() => row.classList.remove("saved"), 1600);
    } catch (err) {
      flash(row, "אין קשר לשרת.", false);
    }
  });
})();
