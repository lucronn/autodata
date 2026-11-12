package main

import (
	"context"
	"crypto"
	"crypto/rand"
	"crypto/rsa"
	"crypto/sha256"
	"crypto/tls"
	"crypto/x509"
	"crypto/x509/pkix"
	"encoding/base64"
	"encoding/json"
	"encoding/pem"
	"errors"
	"fmt"
	"math/big"
	"net"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"sync"
	"sync/atomic"
	"testing"
	"time"

	firebase "firebase.google.com/go/v4"
	"golang.org/x/oauth2"
	"google.golang.org/api/option"
)

type firebaseSDKFixture struct {
	verifier    *firebaseCustomerVerifier
	key         *rsa.PrivateKey
	now         time.Time
	mu          sync.Mutex
	disabled    bool
	deleted     bool
	validSince  int64
	status      int
	delay       time.Duration
	tokenDelay  time.Duration
	tokenCalls  atomic.Int64
	tokenClient *http.Client
	certCalls   atomic.Int64
	userCalls   atomic.Int64
	unexpected  atomic.Int64
}

func newFirebaseSDKFixture(t *testing.T) *firebaseSDKFixture {
	t.Helper()
	for key, value := range map[string]string{"FIREBASE_AUTH_EMULATOR_HOST": "", "GOOGLE_API_GO_EXPERIMENTAL_DISABLE_NEW_AUTH_LIB": "true", "GOOGLE_API_USE_CLIENT_CERTIFICATE": "false", "GOOGLE_API_USE_MTLS_ENDPOINT": "never", "EXPERIMENTAL_GOOGLE_API_USE_S2A": "false"} {
		t.Setenv(key, value)
	}
	f := &firebaseSDKFixture{now: time.Now().UTC().Truncate(time.Second)}
	var err error
	f.key, err = rsa.GenerateKey(rand.Reader, 2048)
	if err != nil {
		t.Fatal(err)
	}
	cert := &x509.Certificate{SerialNumber: big.NewInt(1), Subject: pkix.Name{CommonName: "fixture-token-key"}, NotBefore: f.now.Add(-time.Hour), NotAfter: f.now.Add(time.Hour), KeyUsage: x509.KeyUsageDigitalSignature}
	der, err := x509.CreateCertificate(rand.Reader, cert, cert, &f.key.PublicKey, f.key)
	if err != nil {
		t.Fatal(err)
	}
	certPEM := string(pem.EncodeToMemory(&pem.Block{Type: "CERTIFICATE", Bytes: der}))
	server := httptest.NewTLSServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method == "POST" && r.URL.Path == "/token" {
			f.tokenCalls.Add(1)
			f.mu.Lock()
			delay := f.tokenDelay
			f.mu.Unlock()
			select {
			case <-r.Context().Done():
				return
			case <-time.After(delay):
			}
			w.Header().Set("Content-Type", "application/json")
			// Always expired under OAuth2's refresh margin, forcing each lookup to refresh.
			json.NewEncoder(w).Encode(map[string]any{"access_token": "fixture-access-token", "token_type": "Bearer", "expires_in": 1})
			return
		}
		if r.Method == "GET" && r.URL.Path == "/robot/v1/metadata/x509/securetoken@system.gserviceaccount.com" {
			f.certCalls.Add(1)
			w.Header().Set("Cache-Control", "max-age=3600")
			json.NewEncoder(w).Encode(map[string]string{"fixture-key": certPEM})
			return
		}
		if r.Method == "POST" && r.URL.Path == "/v1/projects/fixture-project/accounts:lookup" {
			f.userCalls.Add(1)
			f.mu.Lock()
			defer f.mu.Unlock()
			if f.delay > 0 {
				select {
				case <-r.Context().Done():
					return
				case <-time.After(f.delay):
				}
			}
			if f.status != 0 {
				w.WriteHeader(f.status)
				json.NewEncoder(w).Encode(map[string]any{"error": map[string]any{"message": "PERMISSION_DENIED"}})
				return
			}
			if f.deleted {
				json.NewEncoder(w).Encode(map[string]any{"users": []any{}})
				return
			}
			json.NewEncoder(w).Encode(map[string]any{"users": []any{map[string]any{"localId": "fixture-user", "disabled": f.disabled, "validSince": strconv.FormatInt(f.validSince, 10)}}})
			return
		}
		f.unexpected.Add(1)
		http.Error(w, "unexpected fixture request", 500)
	}))
	t.Cleanup(server.Close)
	dial := &tls.Dialer{NetDialer: &net.Dialer{}, Config: server.Client().Transport.(*http.Transport).TLSClientConfig.Clone()}
	transport := func(allowed ...string) *http.Transport {
		return &http.Transport{Proxy: nil, DialTLSContext: func(ctx context.Context, network, address string) (net.Conn, error) {
			permitted := false
			for _, host := range allowed {
				permitted = permitted || address == host
			}
			if !permitted {
				f.unexpected.Add(1)
				return nil, errors.New("unexpected SDK destination")
			}
			return dial.DialContext(ctx, network, server.Listener.Addr().String())
		}}
	}
	tokenTransport := transport("oauth2.googleapis.com:443")
	t.Cleanup(tokenTransport.CloseIdleConnections)
	f.tokenClient = &http.Client{Timeout: 10 * time.Second, Transport: firebaseFixtureTransport(func(r *http.Request) (*http.Response, error) {
		if r.Context().Value(firebaseFixtureContextKey{}) != "fixture-context" {
			f.unexpected.Add(1)
			return nil, errors.New("credential context value lost")
		}
		return tokenTransport.RoundTrip(r)
	})}
	previous := http.DefaultTransport
	certTransport := transport("www.googleapis.com:443", "identitytoolkit.googleapis.com:443")
	http.DefaultTransport = certTransport
	t.Cleanup(func() { http.DefaultTransport = previous; certTransport.CloseIdleConnections() })
	userTransport := transport("identitytoolkit.googleapis.com:443")
	t.Cleanup(userTransport.CloseIdleConnections)
	app, err := firebase.NewApp(context.Background(), &firebase.Config{ProjectID: "fixture-project"}, option.WithoutAuthentication(), option.WithHTTPClient(&http.Client{Transport: userTransport, Timeout: 2 * time.Second}))
	if err != nil {
		t.Fatal(err)
	}
	client, err := app.Auth(context.Background())
	if err != nil {
		t.Fatal(err)
	}
	f.verifier = &firebaseCustomerVerifier{client: client, projectID: "fixture-project", now: func() time.Time { return f.now }}
	t.Cleanup(func() {
		if f.unexpected.Load() != 0 {
			t.Errorf("unexpected SDK dials/requests: %d", f.unexpected.Load())
		}
	})
	return f
}
func (f *firebaseSDKFixture) token(t *testing.T, mutate func(map[string]any)) string {
	t.Helper()
	claims := map[string]any{"iss": "https://securetoken.google.com/fixture-project", "aud": "fixture-project", "sub": "fixture-user", "iat": f.now.Unix(), "auth_time": f.now.Unix(), "exp": f.now.Add(time.Hour).Unix(), "firebase": map[string]any{"sign_in_provider": "google.com"}, "organization_id": "untrusted", "roles": []string{"platform_admin"}}
	if mutate != nil {
		mutate(claims)
	}
	header, _ := json.Marshal(map[string]any{"alg": "RS256", "kid": "fixture-key", "typ": "JWT"})
	body, _ := json.Marshal(claims)
	unsigned := base64.RawURLEncoding.EncodeToString(header) + "." + base64.RawURLEncoding.EncodeToString(body)
	digest := sha256.Sum256([]byte(unsigned))
	signature, err := rsa.SignPKCS1v15(rand.Reader, f.key, crypto.SHA256, digest[:])
	if err != nil {
		t.Fatal(err)
	}
	return unsigned + "." + base64.RawURLEncoding.EncodeToString(signature)
}
func TestOfficialFirebaseSDKVerification(t *testing.T) {
	f := newFirebaseSDKFixture(t)
	token := f.token(t, nil)
	identity, err := f.verifier.VerifyLogin(context.Background(), token)
	if err != nil || identity.UID != "fixture-user" || identity.ProjectID != "fixture-project" {
		t.Fatal("valid Firebase token rejected", err)
	}
	if f.certCalls.Load() == 0 || f.userCalls.Load() < 2 {
		t.Fatal("official signature/revocation/auth_time lookups were not exercised")
	}
	for _, tc := range []struct {
		name   string
		mutate func(map[string]any)
	}{
		{"wrong-audience", func(c map[string]any) { c["aud"] = "foreign" }},
		{"wrong-issuer", func(c map[string]any) { c["iss"] = "https://securetoken.google.com/foreign" }},
		{"expired", func(c map[string]any) { c["exp"] = f.now.Unix() - 1 }},
		{"future", func(c map[string]any) { c["iat"] = f.now.Unix() + 61 }},
		{"stale-auth", func(c map[string]any) { c["auth_time"] = f.now.Unix() - 301 }},
		{"missing-auth", func(c map[string]any) { delete(c, "auth_time") }},
		{"non-google", func(c map[string]any) { c["firebase"] = map[string]any{"sign_in_provider": "password"} }},
	} {
		t.Run(tc.name, func(t *testing.T) {
			if _, err := f.verifier.VerifyLogin(context.Background(), f.token(t, tc.mutate)); !errors.Is(err, ErrUnauthenticated) {
				t.Fatal("invalid token accepted", err)
			}
		})
	}
	unknownKey := func() string {
		parts := strings.Split(token, ".")
		header, _ := json.Marshal(map[string]string{"alg": "RS256", "kid": "unknown-key"})
		unsigned := base64.RawURLEncoding.EncodeToString(header) + "." + parts[1]
		digest := sha256.Sum256([]byte(unsigned))
		sig, err := rsa.SignPKCS1v15(rand.Reader, f.key, crypto.SHA256, digest[:])
		if err != nil {
			t.Fatal(err)
		}
		return unsigned + "." + base64.RawURLEncoding.EncodeToString(sig)
	}()
	if _, err := f.verifier.VerifyLogin(context.Background(), unknownKey); !errors.Is(err, ErrUnauthenticated) {
		t.Fatal("unknown signing key accepted", err)
	}
	tampered := token[:len(token)-10] + "AAAAAAAAAA"
	if _, err := f.verifier.VerifyLogin(context.Background(), tampered); !errors.Is(err, ErrUnauthenticated) {
		t.Fatal("tampered signature accepted", err)
	}
	for _, offset := range []int64{-1, 0, 1} {
		f.mu.Lock()
		f.validSince = f.now.Unix() + offset
		f.mu.Unlock()
		err := f.verifier.CheckUser(context.Background(), "fixture-project", "fixture-user", f.now.Unix())
		if (err == nil) != (offset <= 0) {
			t.Fatalf("auth_time boundary%d: %v", offset, err)
		}
	}
	f.mu.Lock()
	f.validSince = f.now.Unix()
	f.mu.Unlock()
	oldAuth := f.token(t, func(c map[string]any) { c["auth_time"] = f.now.Unix() - 1 })
	if _, err := f.verifier.VerifyLogin(context.Background(), oldAuth); !errors.Is(err, ErrUnauthenticated) {
		t.Fatal("fresh iat revived revoked auth_time", err)
	}
	f.mu.Lock()
	f.validSince = 0
	f.disabled = true
	f.mu.Unlock()
	if _, err := f.verifier.VerifyLogin(context.Background(), token); !errors.Is(err, ErrUnauthenticated) {
		t.Fatal("disabled user accepted", err)
	}
	f.mu.Lock()
	f.disabled = false
	f.deleted = true
	f.mu.Unlock()
	if err := f.verifier.CheckUser(context.Background(), "fixture-project", "fixture-user", f.now.Unix()); !errors.Is(err, ErrUnauthenticated) {
		t.Fatal("deleted user accepted", err)
	}
	f.mu.Lock()
	f.deleted = false
	f.status = 403
	f.mu.Unlock()
	if err := f.verifier.CheckUser(context.Background(), "fixture-project", "fixture-user", f.now.Unix()); !errors.Is(err, ErrCustomerDependency) {
		t.Fatal("permission outage not classified safely", fmt.Sprint(err))
	}
}

func TestOfficialFirebaseSDKLookupDeadline(t *testing.T) {
	f := newFirebaseSDKFixture(t)
	f.mu.Lock()
	f.delay = time.Second
	f.mu.Unlock()
	ctx, cancel := context.WithTimeout(context.Background(), 20*time.Millisecond)
	defer cancel()
	started := time.Now()
	if err := f.verifier.CheckUser(ctx, "fixture-project", "fixture-user", f.now.Unix()); !errors.Is(err, ErrCustomerDependency) {
		t.Fatal("timeout did not deny safely", err)
	}
	if time.Since(started) > 300*time.Millisecond {
		t.Fatal("SDK ignored caller deadline")
	}
}

// The ADC regression uses the real token source and SDK with only network endpoints replaced.
type firebaseFixtureContextKey struct{}
type firebaseFixtureTransport func(*http.Request) (*http.Response, error)

func (f firebaseFixtureTransport) RoundTrip(r *http.Request) (*http.Response, error) { return f(r) }

func (f *firebaseSDKFixture) adcContext(t *testing.T, ctx context.Context) context.Context {
	t.Helper()
	path := filepath.Join(t.TempDir(), "adc.json")
	if err := os.WriteFile(path, []byte(`{"type":"authorized_user","client_id":"fixture-client","client_secret":"fixture-secret","refresh_token":"fixture-refresh"}`), 0600); err != nil {
		t.Fatal(err)
	}
	t.Setenv("GOOGLE_APPLICATION_CREDENTIALS", path)
	ctx = context.WithValue(ctx, firebaseFixtureContextKey{}, "fixture-context")
	return context.WithValue(ctx, oauth2.HTTPClient, f.tokenClient)
}

func TestFirebaseADCSurvivesStartupContext(t *testing.T) {
	for _, expired := range []bool{false, true} {
		t.Run(fmt.Sprintf("expired=%t", expired), func(t *testing.T) {
			f := newFirebaseSDKFixture(t)
			var startup context.Context
			var cancel context.CancelFunc
			if expired {
				startup, cancel = context.WithTimeout(context.Background(), 20*time.Millisecond)
			} else {
				startup, cancel = context.WithCancel(context.Background())
			}
			defer cancel()
			verifier, err := newFirebaseCustomerVerifier(f.adcContext(t, startup), customerAuthConfig{ProjectID: "fixture-project"})
			if err != nil {
				t.Fatal("ADC initialization failed", err)
			}
			if expired {
				<-startup.Done()
			} else {
				cancel()
			}
			token := f.token(t, nil)
			for attempt := 0; attempt < 2; attempt++ {
				before := f.tokenCalls.Load()
				identity, err := verifier.VerifyLogin(context.Background(), token)
				if err != nil || identity.UID != "fixture-user" {
					t.Fatal("startup cancellation broke ADC refresh", err)
				}
				if f.tokenCalls.Load() < before+2 {
					t.Fatal("both live user checks must refresh expired credentials")
				}
			}
			for _, expired := range []bool{false, true} {
				var request context.Context
				var stop context.CancelFunc
				if expired {
					request, stop = context.WithDeadline(context.Background(), time.Now().Add(-time.Second))
				} else {
					request, stop = context.WithCancel(context.Background())
					stop()
				}
				started := time.Now()
				_, err := verifier.VerifyLogin(request, token)
				stop()
				if !errors.Is(err, ErrCustomerDependency) || time.Since(started) > 300*time.Millisecond {
					t.Fatal("caller cancellation/deadline did not deny promptly", err)
				}
			}
			if f.tokenClient.Timeout != 10*time.Second {
				t.Fatal("injected HTTP client mutated")
			}
		})
	}
}

func TestFirebaseADCCredentialRefreshHasIndependentTimeout(t *testing.T) {
	f := newFirebaseSDKFixture(t)
	startup, cancel := context.WithCancel(context.Background())
	defer cancel()
	verifier, err := newFirebaseCustomerVerifier(f.adcContext(t, startup), customerAuthConfig{ProjectID: "fixture-project"})
	if err != nil {
		t.Fatal(err)
	}
	cancel()
	f.mu.Lock()
	f.tokenDelay = 5 * time.Second
	f.mu.Unlock()
	started := time.Now()
	err = verifier.CheckUser(context.Background(), "fixture-project", "fixture-user", f.now.Unix())
	elapsed := time.Since(started)
	if !errors.Is(err, ErrCustomerDependency) || f.tokenCalls.Load() == 0 || elapsed < 1500*time.Millisecond || elapsed > 3*time.Second {
		t.Fatalf("refresh was not independently bounded: elapsed=%s requests=%d err=%v", elapsed, f.tokenCalls.Load(), err)
	}
	if f.tokenClient.Timeout != 10*time.Second {
		t.Fatal("injected HTTP client mutated")
	}
}

func TestFirebaseADCRetryRespectsTotalVerifierDeadline(t *testing.T) {
	f := newFirebaseSDKFixture(t)
	verifier, err := newFirebaseCustomerVerifier(f.adcContext(t, context.Background()), customerAuthConfig{ProjectID: "fixture-project"})
	if err != nil {
		t.Fatal(err)
	}
	f.mu.Lock()
	f.tokenDelay = 1600 * time.Millisecond
	f.status = http.StatusServiceUnavailable
	f.mu.Unlock()
	started := time.Now()
	err = verifier.CheckUser(context.Background(), "fixture-project", "fixture-user", f.now.Unix())
	elapsed := time.Since(started)
	if !errors.Is(err, ErrCustomerDependency) || f.tokenCalls.Load() < 2 || elapsed > 2600*time.Millisecond {
		t.Fatalf("retried ADC refresh exceeded total verifier deadline: elapsed=%s token_requests=%d err=%v", elapsed, f.tokenCalls.Load(), err)
	}
}

func TestFirebaseADCCallerCancellationInterruptsRefresh(t *testing.T) {
	f := newFirebaseSDKFixture(t)
	verifier, err := newFirebaseCustomerVerifier(f.adcContext(t, context.Background()), customerAuthConfig{ProjectID: "fixture-project"})
	if err != nil {
		t.Fatal(err)
	}
	f.mu.Lock()
	f.tokenDelay = 5 * time.Second
	f.mu.Unlock()
	caller, cancel := context.WithCancel(context.Background())
	defer cancel()
	result := make(chan error, 1)
	go func() {
		result <- verifier.CheckUser(caller, "fixture-project", "fixture-user", f.now.Unix())
	}()
	waitUntil := time.After(2 * time.Second)
	for f.tokenCalls.Load() == 0 {
		select {
		case <-waitUntil:
			t.Fatal("ADC refresh did not begin")
		case <-time.After(5 * time.Millisecond):
		}
	}
	started := time.Now()
	cancel()
	select {
	case err = <-result:
		if !errors.Is(err, ErrCustomerDependency) || time.Since(started) > 500*time.Millisecond {
			t.Fatalf("canceled caller waited for ADC refresh: elapsed=%s err=%v", time.Since(started), err)
		}
	case <-time.After(500 * time.Millisecond):
		t.Fatal("canceled caller remained blocked on ADC refresh")
	}
}

func TestFirebaseTimedOutSDKCallsHaveBoundedAdmission(t *testing.T) {
	verifier := &firebaseCustomerVerifier{}
	release := make(chan struct{})
	var releaseOnce sync.Once
	finish := func() { releaseOnce.Do(func() { close(release) }) }
	defer finish()
	entered := make(chan struct{}, maxInflightFirebaseSDKCalls+1)
	results := make(chan error, maxInflightFirebaseSDKCalls)
	var callers []context.CancelFunc
	for range maxInflightFirebaseSDKCalls {
		caller, cancel := context.WithCancel(context.Background())
		callers = append(callers, cancel)
		go func() {
			_, err := firebaseCallWithinContext(verifier, caller, func() (int, error) {
				entered <- struct{}{}
				<-release
				return 1, nil
			})
			results <- err
		}()
	}
	for range maxInflightFirebaseSDKCalls {
		select {
		case <-entered:
		case <-time.After(2 * time.Second):
			t.Fatal("SDK calls did not fill the bounded in-flight slots")
		}
	}
	caller, cancel := context.WithTimeout(context.Background(), 25*time.Millisecond)
	_, err := firebaseCallWithinContext(verifier, caller, func() (int, error) {
		entered <- struct{}{}
		return 1, nil
	})
	cancel()
	if !errors.Is(err, context.DeadlineExceeded) || len(entered) != 0 {
		t.Fatalf("saturated SDK call was admitted after caller deadline: err=%v extra_calls=%d", err, len(entered))
	}
	for _, cancel := range callers {
		cancel()
	}
	finish()
	for range maxInflightFirebaseSDKCalls {
		if err := <-results; !errors.Is(err, context.Canceled) {
			t.Fatalf("timed-out SDK call returned an unexpected result: %v", err)
		}
	}
}
