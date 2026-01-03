(function () {
  function byId(id){ return document.getElementById(id); }

  const btn = byId("btnCopy");
  const input = byId("shareLink");
  const msg = byId("copyMsg");

  if (btn && input) {
    btn.addEventListener("click", async () => {
      try {
        await navigator.clipboard.writeText(input.value);
        if (msg) msg.textContent = "Link copiado. Envie no WhatsApp.";
        setTimeout(() => { if (msg) msg.textContent = ""; }, 2000);
      } catch (e) {
        if (msg) msg.textContent = "Falha ao copiar. Copie manualmente.";
      }
    });
  }
})();
