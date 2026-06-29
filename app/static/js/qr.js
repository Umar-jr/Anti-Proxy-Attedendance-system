(async function () {
  const sessionId = window.__SESSION_ID__;
  if (!sessionId) return;

  const img = document.getElementById('qrImg');
  const ttlBox = document.getElementById('qrTtl');

  async function refreshQR() {
    try {
      const res = await fetch('/api/session/' + sessionId + '/qr', { cache: 'no-store' });
      const data = await res.json();
      if (data.png_b64) {
        img.src = 'data:image/png;base64,' + data.png_b64;
        ttlBox.textContent = 'QR expires quickly (about ' + (data.ttl || 30) + ' seconds).';
      }
    } catch (e) {
      ttlBox.textContent = 'Could not refresh QR.';
    }
  }

  await refreshQR();
  setInterval(refreshQR, 15000); // refresh every 15 seconds
})();
