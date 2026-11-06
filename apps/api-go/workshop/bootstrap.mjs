// Choose the entry before loading any application dependencies.
if (new URLSearchParams(location.search).get('demo') === '1') {
  await import('./demo.mjs');
} else {
  await import('./app.mjs');
}
