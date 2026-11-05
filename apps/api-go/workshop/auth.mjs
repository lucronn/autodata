import { requestJSON } from "./catalog.mjs";
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
export function createSession({
  request = requestJSON,
  loadSDK = () => import("./firebase-web.mjs"),
  onChange = () => {},
} = {}) {
  const state = {
    authenticated: false,
    csrf: "",
    ready: false,
    available: false,
    confirm: false,
    message: "",
  };
  let config,
    sdk,
    auth,
    provider,
    epoch = 0,
    preparation,
    retried = false;
  const changed = () => onChange({ ...state });
  const clear = () => {
    epoch++;
    state.authenticated = false;
    state.csrf = "";
    state.ready = false;
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
    async bootstrap({ signal } = {}) {
      const current = ++epoch;
      state.authenticated = false;
      state.csrf = "";
      state.ready = false;
      try {
        config = await request("/auth/config", { signal, timeout: 10000 });
      } catch {
        config = null;
      }
      if (signal?.aborted || current !== epoch) return;
      state.available = validLoginConfig(config);
      try {
        const data = await request("/auth/session", { signal, timeout: 10000 });
        if (signal?.aborted || current !== epoch) return;
        if (!validSession(data)) throw new Error("Invalid session");
        state.authenticated = true;
        state.csrf = data.csrf_token;
        state.message = "Signed in.";
        changed();
      } catch (error) {
        if (signal?.aborted || current !== epoch) return;
        state.authenticated = false;
        state.csrf = "";
        state.message =
          state.available && error.status === 401
            ? "Sign in with Google to open your articles."
            : authMessage(error);
        changed();
        if (state.available && error.status === 401) await prepare(current);
      }
    },
    signIn() {
      if (!state.available || !state.ready || state.authenticated)
        return Promise.reject(new Error("Sign-in is unavailable."));
      const current = epoch;
      state.ready = false;
      changed();
      return (async () => {
        try {
          // Invoke before yielding so the popup starts within the explicit gesture.
          const result = await (state.confirm && auth.currentUser
            ? sdk.reauthenticateWithPopup(auth.currentUser, provider)
            : sdk.signInWithPopup(auth, provider));
          if (current !== epoch) return;
          const token = await sdk.getIdTokenResult(result.user, true);
          if (current !== epoch) return;
          if (
            !Number.isFinite(Date.parse(token.authTime)) ||
            Date.now() - Date.parse(token.authTime) > 300000
          ) {
            const e = new Error();
            e.code = "FRESH_SIGN_IN_REQUIRED";
            throw e;
          }
          try {
            await request("/auth/firebase/session", {
              method: "POST",
              timeout: 10000,
              body: { id_token: token.token },
              headers: { "X-Autodata-Session-Exchange": "1" },
            });
          } catch (error) {
            if (error.status === 401 && !retried)
              error.code = "FRESH_SIGN_IN_REQUIRED";
            throw error;
          }
          if (current !== epoch) return;
          await sdk.signOut(auth);
          const data = await request("/auth/session", { timeout: 10000 });
          if (current !== epoch) return;
          if (!validSession(data)) throw new Error("Invalid session");
          state.authenticated = true;
          state.csrf = data.csrf_token;
          state.confirm = false;
          retried = false;
          state.message = "Signed in.";
        } catch (error) {
          if (current !== epoch) return;
          if (error.code === "FRESH_SIGN_IN_REQUIRED" && !retried) {
            state.confirm = true;
            retried = true;
          } else {
            state.confirm = false;
            await sdk.signOut(auth).catch(() => {});
          }
          state.message = authMessage(error);
        } finally {
          if (current === epoch) {
            state.ready = !state.authenticated;
            changed();
          }
        }
      })();
    },
    async logout() {
      const csrf = state.csrf;
      clear();
      state.message = "Signing out…";
      changed();
      if (sdk && auth) await sdk.signOut(auth).catch(() => {});
      try {
        await request("/auth/logout", {
          method: "POST",
          body: {},
          headers: { "X-CSRF-Token": csrf },
          timeout: 10000,
        });
        state.message = "Signed out.";
        state.ready = false;
        changed();
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
