// Synthetic Google transport only. The application and official Firebase SDK
// remain byte-for-byte production modules. No app or SDK function is replaced.
(() => {
  const registrations = new Map();
  window.addEventListener('message', event => {
    if (!event.data || event.data.fixture !== 'autodata-google-transport') return;
    if (event.origin !== 'https://fixture-project.firebaseapp.com') return;
    for (const callback of registrations.values()) callback({authEvent: event.data.authEvent});
  });
  const frame = {
    restyle: () => Promise.resolve(),
    ping: callback => { callback?.(); return Promise.resolve(); },
    register: (type, callback) => registrations.set(type, callback),
    unregister: type => registrations.delete(type),
    send: (type, payload, callback) => { if (type === 'webStorageSupport') setTimeout(() => { try { callback([{webStorageSupport:true}]); } catch (error) { /* gapi delivers remote callbacks outside the initiating SDK call. */ } }, 0); },
  };
  window.gapi = {
    load: (_name, options) => options.callback(),
    iframes: { CROSS_ORIGIN_IFRAMES_FILTER: () => true, getContext: () => ({open: (_options, callback) => { callback?.(frame); return frame; }}) },
  };
  const callback = new URL(document.currentScript.src).searchParams.get('onload');
  if (callback && typeof window[callback] === 'function') window[callback]();
})();
