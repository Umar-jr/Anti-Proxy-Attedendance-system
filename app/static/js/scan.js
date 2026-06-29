(async function () {
  if (window.__TOKEN_STATUS__ !== 'ok') return;

  const btn = document.getElementById('btnSubmit');
  const statusBox = document.getElementById('statusBox');

  const setStatus = (type, msg) => {
    statusBox.className = 'alert alert-' + type;
    statusBox.textContent = msg;
  };

  btn.addEventListener('click', async () => {
    btn.disabled = true;
    btn.textContent = 'Submitting...';

    try {
      setStatus('info', 'Getting your location...');
      const pos = await getCurrentPosition();
      const lat = pos.coords.latitude;
      const lng = pos.coords.longitude;
      const deviceId = getOrCreateDeviceId();

      setStatus('info', 'Sending attendance...');
      const res = await fetch('/api/attendance/mark', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': window.__CSRF__ || '',
        },
        body: JSON.stringify({ token: window.__TOKEN__, lat, lng, device_id: deviceId }),
      });

      const data = await res.json();
      if (!data.ok) {
        setStatus('danger', data.error || 'Attendance failed');
        btn.disabled = false;
        btn.textContent = 'Submit Attendance';
        return;
      }

      const flagText = data.flagged ? ' (Flagged: device mismatch)' : '';
      setStatus('success', 'Attendance marked successfully. Distance: ' + data.distance_m.toFixed(2) + 'm' + flagText);
      btn.textContent = 'Submitted';
    } catch (e) {
      setStatus('danger', 'Could not submit. Make sure you allowed location permission and try again.');
      btn.disabled = false;
      btn.textContent = 'Submit Attendance';
    }
  });
})();
