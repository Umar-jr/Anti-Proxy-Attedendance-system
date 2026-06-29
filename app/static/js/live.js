(function () {
  const sessionId = window.__SESSION_ID__;
  if (!sessionId) return;

  const tbody = document.getElementById('attBody');

  function addRow(ev) {
    const tr = document.createElement('tr');

    const dt = new Date(ev.marked_at);
    const timeStr = isNaN(dt.getTime()) ? ev.marked_at : dt.toISOString().replace('T', ' ').slice(0, 19);

    const name = (ev.student && ev.student.name) ? ev.student.name : '';
    const matric = (ev.student && ev.student.matric) ? ev.student.matric : '';
    const dist = (typeof ev.distance_m === 'number') ? ev.distance_m.toFixed(2) : '';
    const flag = ev.flagged ? 'YES' : 'NO';

    tr.innerHTML = '<td>' + escapeHtml(name) + '</td>' +
      '<td>' + escapeHtml(matric || '') + '</td>' +
      '<td>' + escapeHtml(timeStr) + '</td>' +
      '<td>' + escapeHtml(dist) + '</td>' +
      '<td>' + escapeHtml(flag) + '</td>';

    // Prepend to top
    if (tbody.firstChild) {
      tbody.insertBefore(tr, tbody.firstChild);
    } else {
      tbody.appendChild(tr);
    }
  }

  function escapeHtml(s) {
    return String(s)
      .replaceAll('&', '&amp;')
      .replaceAll('<', '&lt;')
      .replaceAll('>', '&gt;')
      .replaceAll('"', '&quot;')
      .replaceAll("'", '&#039;');
  }

  const es = new EventSource('/lecturer/session/' + sessionId + '/stream');

  es.addEventListener('ping', () => {
    // connected
  });

  es.addEventListener('attendance', (msg) => {
    try {
      const ev = JSON.parse(msg.data);
      addRow(ev);
    } catch (e) {
      // ignore
    }
  });

  es.onerror = () => {
    // browser will auto-reconnect
  };
})();
