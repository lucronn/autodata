package main

import (
	"context"
	"encoding/json"
	"errors"
	"net"
	"net/url"
	"os"
	"regexp"
	"strings"
	"unicode"
	"unicode/utf8"
)

type customerAuthConfig struct {
	Environment, Mode, Origin, ProjectID, APIKey, AppID, AuthDomain string
	commerceMode                                                    string
	stagingTesterUIDs                                               map[string]struct{}
}

func loadCustomerAuthConfig(getenv func(string) string) (customerAuthConfig, error) {
	c := customerAuthConfig{Environment: getenv("AUTODATA_ENV"), Mode: getenv("AUTODATA_AUTH_MODE"), Origin: getenv("AUTODATA_PUBLIC_ORIGIN"), ProjectID: getenv("AUTODATA_FIREBASE_PROJECT_ID"), APIKey: getenv("AUTODATA_FIREBASE_WEB_API_KEY"), AppID: getenv("AUTODATA_FIREBASE_WEB_APP_ID"), AuthDomain: getenv("AUTODATA_FIREBASE_AUTH_DOMAIN"), commerceMode: getenv("AUTODATA_COMMERCE_MODE")}
	invalid := errors.New("customer authentication configuration is invalid")
	switch c.Environment {
	case "development", "test", "staging", "production":
	default:
		return c, invalid
	}
	if c.Mode != "firebase" && c.Mode != "local" {
		return c, invalid
	}
	if c.Mode == "local" && c.Environment != "development" && c.Environment != "test" {
		return c, invalid
	}
	origin, err := url.Parse(c.Origin)
	if err != nil || origin.Host == "" || origin.User != nil || origin.Path != "" || origin.RawQuery != "" || origin.Fragment != "" || origin.Opaque != "" {
		return c, invalid
	}
	loopback := origin.Hostname() == "localhost"
	if ip := net.ParseIP(origin.Hostname()); ip != nil {
		loopback = ip.IsLoopback()
	}
	if origin.Scheme != "https" && !(c.Environment == "test" && origin.Scheme == "http" && loopback) {
		return c, invalid
	}
	if c.Environment == "production" && c.Origin != "https://cars.tk" && c.Origin != "https://autodata.cars.tk" {
		return c, invalid
	}
	if c.Mode == "local" {
		return c, nil
	}
	if getenv("FIREBASE_AUTH_EMULATOR_HOST") != "" {
		return c, invalid
	}
	if !regexp.MustCompile(`^[a-z][a-z0-9-]{4,28}[a-z0-9]$`).MatchString(c.ProjectID) || c.APIKey == "" || strings.TrimSpace(c.APIKey) != c.APIKey || !regexp.MustCompile(`^1:[0-9]+:web:[a-zA-Z0-9]+$`).MatchString(c.AppID) {
		return c, invalid
	}
	if c.AuthDomain != c.ProjectID+".firebaseapp.com" && c.AuthDomain != origin.Hostname() {
		return c, invalid
	}
	raw := getenv("AUTODATA_WORKSHOP_TESTER_UIDS_JSON")
	if c.restrictedStagingTesters() || (c.Environment == "staging" && c.commerceMode == "disabled" && raw != "") {
		// Reuse strict Unicode validation: encoding/json replaces lone surrogates.
		if workshopProductionOrigin(c.Origin) || len(raw) > 32768 || !purchaseUnicodeValid([]byte(raw)) {
			return c, invalid
		}
		var uids []string
		if json.Unmarshal([]byte(raw), &uids) != nil || len(uids) < 1 || len(uids) > 100 {
			return c, invalid
		}
		c.stagingTesterUIDs = make(map[string]struct{}, len(uids))
		for _, uid := range uids {
			if uid == "" || utf8.RuneCountInString(uid) > 128 || strings.TrimSpace(uid) == "" || strings.ContainsFunc(uid, unicode.IsControl) {
				return customerAuthConfig{}, invalid
			}
			if _, exists := c.stagingTesterUIDs[uid]; exists {
				return customerAuthConfig{}, invalid
			}
			c.stagingTesterUIDs[uid] = struct{}{}
		}
	}
	return c, nil
}

func (c customerAuthConfig) restrictedStagingTesters() bool {
	return c.Environment == "staging" && (c.commerceMode == "stripe_test" ||
		(c.commerceMode == "disabled" && c.stagingTesterUIDs != nil))
}

func (c customerAuthConfig) allowsTester(projectID, uid string) bool {
	if !c.restrictedStagingTesters() {
		return true
	}
	_, allowed := c.stagingTesterUIDs[uid]
	return projectID == c.ProjectID && uid != "" && allowed
}

// newConfiguredCustomerAuth validates persistence before any cloud adapter is
// initialized. Tests inject the same official verifier with an isolated transport.
func newConfiguredCustomerAuth(ctx context.Context, c customerAuthConfig, store customerSessionStore, verifier CustomerIdentityVerifier) (*customerAuthService, error) {
	if c.restrictedStagingTesters() && len(c.stagingTesterUIDs) == 0 {
		return nil, ErrCustomerDependency
	}
	service := &customerAuthService{config: c, store: store, verifier: verifier}
	if c.Mode == "local" {
		return service, nil
	}
	if c.Mode != "firebase" || os.Getenv("FIREBASE_AUTH_EMULATOR_HOST") != "" || store == nil {
		return nil, ErrCustomerDependency
	}
	if _, ok := store.(*postgresCustomerSessions); !ok {
		return nil, ErrCustomerDependency
	}
	if err := store.CheckSchema(ctx); err != nil {
		return nil, ErrCustomerDependency
	}
	if verifier == nil {
		var err error
		service.verifier, err = newFirebaseCustomerVerifier(ctx, c)
		if err != nil {
			return nil, err
		}
	}
	return service, nil
}
