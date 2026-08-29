function applyClientClass() {
  const root = document.documentElement;
  if (root.getAttribute("data-view-locked") === "1") return;
  const mobile = window.matchMedia("(max-width: 768px)").matches;
  const client = mobile ? "mobile" : "desktop";
  root.classList.toggle("client-mobile", client === "mobile");
  root.classList.toggle("client-desktop", client === "desktop");
  document.body.classList.toggle("client-mobile", client === "mobile");
  document.body.classList.toggle("client-desktop", client === "desktop");
  root.setAttribute("data-client", client);
}

function setupNav() {
  const header = document.querySelector(".site-header");
  const toggle = document.querySelector(".nav-toggle");
  const nav = document.getElementById("site-nav");
  if (!header || !toggle || !nav) return;
  toggle.addEventListener("click", () => {
    const open = header.classList.toggle("nav-open");
    toggle.setAttribute("aria-expanded", open ? "true" : "false");
  });
  nav.querySelectorAll("a").forEach((link) => {
    link.addEventListener("click", () => {
      header.classList.remove("nav-open");
      toggle.setAttribute("aria-expanded", "false");
    });
  });
}

applyClientClass();
window.addEventListener("resize", applyClientClass);
document.addEventListener("DOMContentLoaded", () => {
  applyClientClass();
  setupNav();
});
document.body.addEventListener("htmx:afterSwap", applyClientClass);
