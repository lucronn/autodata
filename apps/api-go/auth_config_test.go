package main

import (
	"encoding/json"
	"strings"
	"testing"
)

func identityTestConfig() map[string]string {
	return map[string]string{"AUTODATA_ENV": "test", "AUTODATA_AUTH_MODE": "firebase", "AUTODATA_PUBLIC_ORIGIN": "https://cars.example", "AUTODATA_FIREBASE_PROJECT_ID": "fixture-project", "AUTODATA_FIREBASE_WEB_API_KEY": "public-fixture-key", "AUTODATA_FIREBASE_WEB_APP_ID": "1:123:web:abc", "AUTODATA_FIREBASE_AUTH_DOMAIN": "fixture-project.firebaseapp.com"}
}
func TestCustomerAuthConfiguration(t *testing.T) {
	read := func(m map[string]string) func(string) string { return func(k string) string { return m[k] } }
	if _, err := loadCustomerAuthConfig(read(identityTestConfig())); err != nil {
		t.Fatal(err)
	}
	for _, key := range []string{"AUTODATA_ENV", "AUTODATA_AUTH_MODE", "AUTODATA_PUBLIC_ORIGIN", "AUTODATA_FIREBASE_PROJECT_ID", "AUTODATA_FIREBASE_WEB_API_KEY", "AUTODATA_FIREBASE_WEB_APP_ID", "AUTODATA_FIREBASE_AUTH_DOMAIN"} {
		t.Run("missing_"+key, func(t *testing.T) {
			m := identityTestConfig()
			delete(m, key)
			if _, err := loadCustomerAuthConfig(read(m)); err == nil {
				t.Fatal("missing configuration accepted")
			}
		})
	}
	for _, tc := range []struct{ key, value string }{{"AUTODATA_ENV", "unknown"}, {"AUTODATA_AUTH_MODE", "oidc"}, {"FIREBASE_AUTH_EMULATOR_HOST", "localhost:9099"}, {"AUTODATA_PUBLIC_ORIGIN", "https://cars.example/path"}, {"AUTODATA_PUBLIC_ORIGIN", "http://cars.example"}, {"AUTODATA_FIREBASE_AUTH_DOMAIN", "other.firebaseapp.com"}} {
		t.Run(tc.key+tc.value, func(t *testing.T) {
			m := identityTestConfig()
			m[tc.key] = tc.value
			if _, err := loadCustomerAuthConfig(read(m)); err == nil {
				t.Fatal("unsafe configuration accepted")
			}
		})
	}
	for _, env := range []string{"development", "test", "staging", "production"} {
		m := map[string]string{"AUTODATA_ENV": env, "AUTODATA_AUTH_MODE": "local", "AUTODATA_PUBLIC_ORIGIN": "https://cars.tk"}
		_, err := loadCustomerAuthConfig(read(m))
		if (err == nil) != (env == "development" || env == "test") {
			t.Fatalf("local mode env %s: %v", env, err)
		}
	}
	for _, origin := range []string{"https://autodata.cars.tk", "https://cars.tk"} {
		for _, domain := range []string{"fixture-project.firebaseapp.com", origin[len("https://"):]} {
			t.Run("production_"+origin+"_"+domain, func(t *testing.T) {
				m := identityTestConfig()
				m["AUTODATA_ENV"] = "production"
				m["AUTODATA_PUBLIC_ORIGIN"] = origin
				m["AUTODATA_FIREBASE_AUTH_DOMAIN"] = domain
				c, err := loadCustomerAuthConfig(read(m))
				if err != nil || c.Origin != origin {
					t.Fatalf("origin %q: got %q, error %v", origin, c.Origin, err)
				}
				m["FIREBASE_AUTH_EMULATOR_HOST"] = "localhost:9099"
				if _, err := loadCustomerAuthConfig(read(m)); err == nil {
					t.Fatal("production emulator accepted")
				}
			})
		}
	}
	for _, origin := range []string{
		"https://other.example", "https://www.cars.tk", "https://evil.autodata.cars.tk",
		"https://autodata.cars.tk.evil.example", "http://autodata.cars.tk",
		"https://autodata.cars.tk/", "https://autodata.cars.tk/workshop/",
		"https://autodata.cars.tk:443", "https://user@autodata.cars.tk",
		"https://autodata.cars.tk?q=1", "https://autodata.cars.tk#fragment",
		"https://autodata.cars.tk.", "https://AUTODATA.cars.tk",
	} {
		t.Run("production_denied_"+origin, func(t *testing.T) {
			m := identityTestConfig()
			m["AUTODATA_ENV"] = "production"
			m["AUTODATA_PUBLIC_ORIGIN"] = origin
			if _, err := loadCustomerAuthConfig(read(m)); err == nil {
				t.Fatal("production non-canonical origin accepted")
			}
		})
	}
}

func stagingTesterTestConfig(t *testing.T, raw string) customerAuthConfig {
	t.Helper()
	m := identityTestConfig()
	m["AUTODATA_ENV"] = "staging"
	m["AUTODATA_COMMERCE_MODE"] = "stripe_test"
	m["AUTODATA_WORKSHOP_TESTER_UIDS_JSON"] = raw
	c, err := loadCustomerAuthConfig(func(k string) string { return m[k] })
	if err != nil {
		t.Fatal(err)
	}
	return c
}
func TestStagingTesterConfigurationFailsClosed(t *testing.T) {
	many := make([]string, 101)
	for i := range many {
		many[i] = strings.Repeat("x", i+1)
	}
	manyJSON, _ := json.Marshal(many)
	malformed := []string{" ", `null`, `[]`, `{}`, `"fixture-user"`, `[null]`, `[42]`, `["fixture-user","fixture-user"]`, `["x"] []`, `[""]`, `["   "]`, `["a\nb"]`, `["\ud800"]`, string([]byte{'[', '"', 255, '"', ']'}), `["` + strings.Repeat("x", 129) + `"]`, string(manyJSON), strings.Repeat(" ", 32769) + `["x"]`}
	for _, mode := range []string{"stripe_test", "disabled"} {
		t.Run(mode, func(t *testing.T) {
			m := identityTestConfig()
			m["AUTODATA_ENV"] = "staging"
			m["AUTODATA_COMMERCE_MODE"] = mode
			read := func(k string) string { return m[k] }
			if mode == "stripe_test" {
				if _, err := loadCustomerAuthConfig(read); err == nil {
					t.Error("missing staging tester list accepted for TEST payments")
				}
			}
			for _, raw := range malformed {
				m["AUTODATA_WORKSHOP_TESTER_UIDS_JSON"] = raw
				_, err := loadCustomerAuthConfig(read)
				if err == nil {
					t.Errorf("malformed staging tester configuration accepted (length %d)", len(raw))
				} else if err.Error() != "customer authentication configuration is invalid" {
					t.Fatal("configuration error disclosed details")
				}
			}
			m["AUTODATA_WORKSHOP_TESTER_UIDS_JSON"] = `["fixture-user"]`
			for _, origin := range []string{"https://cars.tk", "https://autodata.cars.tk"} {
				m["AUTODATA_PUBLIC_ORIGIN"] = origin
				if _, err := loadCustomerAuthConfig(read); err == nil {
					t.Error("production origin accepted as restricted staging")
				}
			}
		})
	}
	stagingTesterTestConfig(t, `["fixture-user","second-user"]`)
	stagingTesterTestConfig(t, `["`+strings.Repeat("é", 128)+`"]`)
}
func TestStagingTesterConfigurationDoesNotAffectOtherModes(t *testing.T) {
	for _, environment := range []string{"test", "development", "staging", "production"} {
		for _, mode := range []string{"", "disabled", "read_only", "stripe_live", "stripe_test"} {
			if environment == "staging" && (mode == "stripe_test" || mode == "disabled") {
				continue
			}
			m := identityTestConfig()
			m["AUTODATA_ENV"] = environment
			m["AUTODATA_COMMERCE_MODE"] = mode
			m["AUTODATA_WORKSHOP_TESTER_UIDS_JSON"] = "malformed ignored outside restricted mode"
			if environment == "production" {
				m["AUTODATA_PUBLIC_ORIGIN"] = "https://cars.tk"
			}
			c, err := loadCustomerAuthConfig(func(k string) string { return m[k] })
			if err != nil || !c.allowsTester("unlisted-project", "unlisted-user") {
				t.Errorf("unrelated mode changed %s/%s: %v", environment, mode, err)
			}
		}
	}
}

func TestDisabledStagingTesterConfigurationOptsIn(t *testing.T) {
	m := identityTestConfig()
	m["AUTODATA_ENV"] = "staging"
	m["AUTODATA_COMMERCE_MODE"] = "disabled"
	read := func(k string) string { return m[k] }
	legacy, err := loadCustomerAuthConfig(read)
	if err != nil || !legacy.allowsTester("fixture-project", "unlisted-user") {
		t.Fatalf("legacy disabled staging with no tester list changed: %v", err)
	}
	m["AUTODATA_WORKSHOP_TESTER_UIDS_JSON"] = `["approved-user","second-user"]`
	config, err := loadCustomerAuthConfig(read)
	if err != nil {
		t.Fatal(err)
	}
	delete(m, "AUTODATA_WORKSHOP_TESTER_UIDS_JSON")
	for _, tc := range []struct {
		project, uid string
		allowed      bool
	}{
		{"fixture-project", "approved-user", true},
		{"fixture-project", "second-user", true},
		{"fixture-project", "unlisted-user", false},
		{"another-project", "approved-user", false},
		{"fixture-project", "", false},
	} {
		if got := config.allowsTester(tc.project, tc.uid); got != tc.allowed {
			t.Errorf("disabled staging audience for %s/%s: allowed %v, want %v", tc.project, tc.uid, got, tc.allowed)
		}
	}
}

func TestStagingTesterConfigIsFrozenAfterEnvironmentChange(t *testing.T) {
	m := identityTestConfig()
	m["AUTODATA_ENV"] = "staging"
	m["AUTODATA_COMMERCE_MODE"] = "stripe_test"
	m["AUTODATA_WORKSHOP_TESTER_UIDS_JSON"] = `["original-user"]`
	c, err := loadCustomerAuthConfig(func(k string) string { return m[k] })
	if err != nil {
		t.Fatal(err)
	}
	m["AUTODATA_WORKSHOP_TESTER_UIDS_JSON"] = `["replacement-user"]`
	m["AUTODATA_COMMERCE_MODE"] = "disabled"
	if !c.allowsTester("fixture-project", "original-user") || c.allowsTester("fixture-project", "replacement-user") {
		t.Fatal("live environment change mutated audience")
	}
}
