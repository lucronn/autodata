// The fictional layout sample is separate from the real-data test checkout.
const params = new URLSearchParams(location.search);
if (params.get('sample') === '1' && params.get('demo') !== '1') {
  await import('./demo.mjs');
} else {
  let testCheckoutReady = false;
  try {
    const response = await fetch('/workshop/demo-mode.json', { cache: 'no-store', credentials: 'same-origin' });
    if (response.ok) {
      const status = await response.json();
      testCheckoutReady = status?.enabled === true && Object.keys(status).length === 1;
    }
  } catch {
    // An unavailable mode handshake must never be labeled a no-charge checkout.
  }
  if (params.get('demo') === '1' && !testCheckoutReady) {
    document.getElementById('test-unavailable').hidden = false;
    document.querySelector('.site-header nav').hidden = true;
    document.querySelector('main').hidden = true;
  } else {
    document.getElementById('test-banner').hidden = !testCheckoutReady;
    await import('./app.mjs');
  }
}
