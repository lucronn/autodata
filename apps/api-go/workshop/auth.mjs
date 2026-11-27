import * as catalog from "./catalog.mjs";
import { validScope } from "./commerce.mjs";

const { requestJSON, selectedIndexSessionPreference } = catalog;
export function validLoginConfig(config) {
  const f = config?.firebase;
  return Boolean(
    config?.version === "v1" &&
      config.mode === "firebase" &&
      config.login_available === true &&
      config.providers?.includes("google.com") &&
      f &&
      ["apiKey", "authDomain", "projectId", "appId"].every(
        (k) =>
          typeof f[k] === "string" && f[k].trim() === f[k] && f[k].length > 0,
      ) &&
      /^[a-z][a-z0-9-]{4,28}[a-z0-9]$/.test(f.projectId) &&
      /^1:[0-9]+:web:[a-zA-Z0-9]+$/.test(f.appId) &&
      (f.authDomain === `${f.projectId}.firebaseapp.com` ||
        f.authDomain === globalThis.location?.hostname),
  );
}
const validSession = (data) =>
  data?.authenticated === true &&
  Array.isArray(data.roles) &&
  data.roles.includes("dataset_viewer") &&
  typeof data.csrf_token === "string" &&
  data.csrf_token.length > 0 &&
  Number.isFinite(Date.parse(data.expires_at)) &&
  Date.parse(data.expires_at) > Date.now();
export function authMessage(error) {
  if (error?.code === "auth/popup-blocked")
    return "Your browser blocked sign-in. Allow the popup and try again.";
  if (
    ["auth/popup-closed-by-user", "auth/cancelled-popup-request"].includes(
      error?.code,
    )
  )
    return "Google sign-in was canceled. You can try again.";
  if (error?.code === "FRESH_SIGN_IN_REQUIRED")
    return "Confirm Google sign-in to continue.";
  if (error?.status === 503)
    return "Sign-in is temporarily unavailable. Try again.";
  if (error?.status === 403)
    return "This account cannot sign in. Contact support.";
  if (error?.status === 401) return "Your session has expired. Sign in again.";
  return "Google sign-in is unavailable. You can keep browsing.";
}
export function readSessionBootstrap(request = requestJSON, { signal, includeLibrary = false, route } = {}) {
  const read = async (path, headers) => {
    try {
      return { status: "fulfilled", value: await request(path, { signal, timeout: 10000, headers }) };
    } catch (reason) {
      return { status: "rejected", reason };
    }
  };
  let path = "/auth/session";
  let prefer = "workshop-session-mode";
  if (includeLibrary) {
    prefer += ", workshop-session-library";
  } else if (route && !["year", "view", "order", "article", "q"].some(key => route.has(key))) {
    const scope = { configuration_id: route.get("configuration"), region: route.get("region") };
    if (validScope(scope) && route.getAll("configuration").length === 1 && route.getAll("region").length === 1) {
      path += "?" + new URLSearchParams(scope);
      prefer += ", workshop-session-article-index";
    }
  }
  return [read("/auth/config"), read(path, { Prefer: prefer })];
}
export function createSession({
  request = requestJSON,
  loadSDK = () => import("./firebase-web.mjs"),
  onChange = () => {},
} = {}) {
  const state = {
    mode: null,
    authenticated: false,
    csrf: "",
    ready: false,
    available: false,
    popupPending: false,
    confirm: false,
    message: "",
  };
  let config,
    pendingLoginConfiguration,
    sdk,
    auth,
    provider,
    epoch = 0,
    preparation,
    guestRefresh,
    selectedIndexConfirmation,
    retried = false;
  const changed = () => onChange({ ...state });
  const configureLogin = (result) => {
    config = result.status === "fulfilled" ? result.value : null;
    state.mode = ["local", "firebase"].includes(config?.mode) ? config.mode : null;
    state.available = validLoginConfig(config);
  };
  const stopGuestRefresh = () => {
    guestRefresh?.abort();
    guestRefresh = null;
  };
  const clear = () => {
    epoch++;
    stopGuestRefresh();
    selectedIndexConfirmation?.abort();
    state.mode = null;
    state.authenticated = false;
    state.csrf = "";
    state.ready = false;
    state.popupPending = false;
    changed();
  };
  async function prepare(current) {
    if (auth) {
      try {
        if (!provider) provider = new sdk.GoogleAuthProvider();
        await sdk.setPersistence(auth, sdk.inMemoryPersistence);
        if (current === epoch) {
          state.ready = true;
          changed();
        }
      } catch (error) {
        if (current !== epoch) return;
        state.ready = false;
        state.message = authMessage(error);
        changed();
      }
      return;
    }
    if (preparation) {
      await preparation;
      preparation = null;
      return prepare(current);
    }
    preparation = (async () => {
      sdk = await loadSDK();
      if (current !== epoch) return;
      auth = sdk.initializeAuth(
        sdk.initializeApp(config.firebase, "autodata-workshop"),
        {
          persistence: sdk.inMemoryPersistence,
          popupRedirectResolver: sdk.browserPopupRedirectResolver,
        },
      );
      provider = new sdk.GoogleAuthProvider();
      await sdk.setPersistence(auth, sdk.inMemoryPersistence);
      if (current !== epoch) return;
      state.ready = true;
      changed();
    })();
    try {
      await preparation;
    } catch (error) {
      if (current !== epoch) return;
      state.ready = false;
      state.message = authMessage(error);
      changed();
    }
  }
  return {
    state,
    clear,
    async matchesCurrentSession({ signal } = {}) {
      const current = epoch;
      const csrf = state.csrf;
      const data = await request("/auth/session", { signal, timeout: 10000 });
      return !signal?.aborted && current === epoch && state.authenticated &&
        csrf === state.csrf && validSession(data) && data.csrf_token === csrf;
    },
    async bootstrap({ signal, initial, preserveGuestSignIn = false } = {}) {
      const current = ++epoch;
      stopGuestRefresh();
      const wasReady = state.ready || state.popupPending;
      // A prepared guest sign-in can remain available during a picker focus refresh.
      // Any authenticated session still needs a fresh check before use.
      const keepGuestSignIn = preserveGuestSignIn && !initial && state.mode === "firebase" &&
        !state.authenticated && state.available && state.ready && !state.popupPending;
      selectedIndexConfirmation?.abort();
      pendingLoginConfiguration = null;
      if (!keepGuestSignIn) state.mode = null;
      state.authenticated = false;
      state.csrf = "";
      state.ready = keepGuestSignIn;
      state.popupPending = false;
      if (wasReady && !keepGuestSignIn) changed();
      const initialResult = initial ? await initial : null;
      if (signal?.aborted || current !== epoch) return;
      const refresh = keepGuestSignIn ? new AbortController() : null;
      guestRefresh = refresh;
      const readSignal = refresh && signal ? AbortSignal.any([refresh.signal, signal]) : refresh?.signal ?? signal;
      const [configuration, response] = initialResult ?? readSessionBootstrap(request, { signal: readSignal });
      const session = await response;
      if (guestRefresh === refresh) guestRefresh = null;
      if (signal?.aborted || current !== epoch) return;
      const data = session.status === "fulfilled" ? session.value : null;
      const confirmedMode = validSession(data) && data.mode === "firebase";
      if (confirmedMode) {
        // The checked session can open owned data while public login settings load.
        pendingLoginConfiguration = configuration;
        state.mode = data.mode;
        state.available = false;
      } else {
        const settings = await configuration;
        if (signal?.aborted || current !== epoch) return;
        configureLogin(settings);
      }
      if (confirmedMode || validSession(data)) {
        state.authenticated = true;
        state.csrf = data.csrf_token;
        state.ready = false;
        state.message = "Signed in.";
        changed();
        return confirmedMode ? data.workshop_library ?? data.workshop_article_index : undefined;
      }
      const error = session.status === "rejected" ? session.reason : null;
      const guest = error?.status === 401;
      state.ready = keepGuestSignIn && guest && state.available;
      state.message = state.available && guest
        ? "Sign in with Google to open your articles."
        : authMessage(error);
      changed();
      if (state.available && guest && !state.ready) await prepare(current);
    },
    signIn({ confirmSelectedIndex } = {}) {
      // App assets can span releases during a rolling deployment.
      const useSelectedIndex = typeof selectedIndexSessionPreference === "string" &&
        typeof confirmSelectedIndex === "function";
      if (!state.available || (!state.ready && !state.popupPending) || state.authenticated)
        return Promise.reject(new Error("Sign-in is unavailable."));
      // Firebase cancels the previous popup when a new one opens. Only this
      // attempt may exchange a token or update the customer session.
      const current = ++epoch;
      // A pending guest response can expire the cookie issued by the exchange.
      stopGuestRefresh();
      state.ready = false;
      state.popupPending = true;
      state.message = "Continue in the Google sign-in window.";
      changed();
      return (async () => {
        try {
          // Invoke before yielding so the popup starts within the explicit gesture.
          const result = await (state.confirm && auth.currentUser
            ? sdk.reauthenticateWithPopup(auth.currentUser, provider)
            : sdk.signInWithPopup(auth, provider));
          if (current !== epoch) return;
          state.popupPending = false;
          state.message = "Finishing sign-in…";
          changed();
          let token = await sdk.getIdTokenResult(result.user);
          if (current !== epoch) return;
          const issuedAge = Date.now() - Date.parse(token.issuedAtTime);
          // Leave time for the exchange within the server's five-minute window.
          if (!Number.isFinite(issuedAge) || issuedAge < -60000 || issuedAge > 240000) {
            token = await sdk.getIdTokenResult(result.user, true);
            if (current !== epoch) return;
          }
          if (
            !Number.isFinite(Date.parse(token.authTime)) ||
            Date.now() - Date.parse(token.authTime) > 300000
          ) {
            const e = new Error();
            e.code = "FRESH_SIGN_IN_REQUIRED";
            throw e;
          }
          let exchangeCSRF = null;
          try {
            await request("/auth/firebase/session", {
              method: "POST",
              timeout: 10000,
              body: { id_token: token.token },
              headers: {
                "X-Autodata-Session-Exchange": "1",
                ...(useSelectedIndex ? { Prefer: selectedIndexSessionPreference } : {}),
              },
              ...(useSelectedIndex ? {
                onSelectedIndexSession(receipt) { exchangeCSRF = receipt.exchangeCSRF; },
              } : {}),
            });
          } catch (error) {
            if (error.status === 401 && !retried)
              error.code = "FRESH_SIGN_IN_REQUIRED";
            throw error;
          }
          if (current !== epoch) return;
          await sdk.signOut(auth);
          if (current !== epoch) return;
          let confirmedIndex, confirmedSession;
          if (exchangeCSRF) {
            const confirmation = new AbortController();
            selectedIndexConfirmation = confirmation;
            try {
              const index = await confirmSelectedIndex(exchangeCSRF, confirmation.signal);
              const data = { authenticated: true, roles: ["dataset_viewer"],
                expires_at: index?.expiresAt, csrf_token: exchangeCSRF };
              if (validSession(data)) {
                confirmedIndex = index.firstIndex;
                confirmedSession = data;
              }
            } finally {
              confirmation.abort();
              if (selectedIndexConfirmation === confirmation) selectedIndexConfirmation = null;
            }
          }
          if (current !== epoch) return;
          const data = confirmedSession ?? await request("/auth/session", { timeout: 10000 });
          if (current !== epoch) return;
          if (!validSession(data) || (exchangeCSRF && data.csrf_token !== exchangeCSRF))
            throw new Error("Invalid session");
          state.authenticated = true;
          state.csrf = data.csrf_token;
          state.confirm = false;
          retried = false;
          state.message = "Signed in.";
          return confirmedIndex;
        } catch (error) {
          if (current !== epoch) return;
          if (state.popupPending) {
            state.popupPending = false;
            changed();
          }
          if (error.code === "FRESH_SIGN_IN_REQUIRED" && !retried) {
            state.confirm = true;
            retried = true;
          } else {
            state.confirm = false;
            await sdk.signOut(auth).catch(() => {});
          }
          if (current !== epoch) return;
          state.message = authMessage(error);
        } finally {
          if (current === epoch) {
            state.popupPending = false;
            state.ready = !state.authenticated;
            changed();
          }
        }
      })();
    },
    async logout() {
      const csrf = state.csrf;
      clear();
      const current = epoch;
      state.message = "Signing out…";
      changed();
      const firebaseLogout = sdk && auth
        ? Promise.resolve().then(() => sdk.signOut(auth)).catch(() => {})
        : null;
      try {
        await Promise.all([
          request("/auth/logout", {
            method: "POST",
            body: {},
            headers: { "X-CSRF-Token": csrf },
            timeout: 10000,
          }),
          firebaseLogout,
        ]);
        state.message = "Signed out.";
        state.ready = false;
        changed();
        if (pendingLoginConfiguration) {
          const settings = await pendingLoginConfiguration;
          if (current !== epoch) return true;
          pendingLoginConfiguration = null;
          configureLogin(settings);
        }
        if (state.available) await prepare(epoch);
        return true;
      } catch {
        state.message = "Sign-out could not be confirmed. Retry sign-out.";
        state.csrf = csrf;
        changed();
        return false;
      }
    },
  };
}
