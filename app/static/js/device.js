function getOrCreateDeviceId() {
  const key = 'qr_attendance_device_id';
  let id = localStorage.getItem(key);
  if (id) return id;

  // simple random ID (not fingerprinting, just a lightweight device token)
  id = 'dev_' + Math.random().toString(36).slice(2) + '_' + Date.now().toString(36);
  localStorage.setItem(key, id);
  return id;
}
