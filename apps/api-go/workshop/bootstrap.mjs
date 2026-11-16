// The fictional layout sample is separate from the real-data test checkout.
const params = new URLSearchParams(location.search);
if (params.get('sample') === '1' && params.get('demo') !== '1') {
  await import('./demo.mjs');
} else {
  let testCheckoutReady = false;
  let openDemoReady = false;
  try {
    const response = await fetch('/workshop/demo-mode.json', { cache: 'no-store', credentials: 'same-origin' });
    if (response.ok) {
      const status = await response.json();
      testCheckoutReady = status?.enabled === true && Object.keys(status).length === 1;
      openDemoReady = status?.enabled === true && status?.access === 'open' && Object.keys(status).length === 2;
    }
  } catch {
    // An unavailable mode handshake must never be labeled a no-charge checkout.
  }
  if (params.get('demo') === '1' && !testCheckoutReady && !openDemoReady) {
    document.getElementById('test-unavailable').hidden = false;
    document.querySelector('.site-header nav').hidden = true;
    document.querySelector('main').hidden = true;
  } else {
    document.getElementById('test-banner').hidden = !testCheckoutReady;
    document.getElementById('open-demo-banner').hidden = !(params.get('demo') === '1' && openDemoReady);
    document.documentElement.dataset.workshopMode = params.get('demo') === '1' && openDemoReady ? 'open-demo' : 'regular';
    await import('./app.mjs');
  }
}
