package main

import (
	"errors"
	"net"
	"net/url"
	"regexp"
	"strings"
)

type customerAuthConfig struct {
	Environment, Mode, Origin, ProjectID, APIKey, AppID, AuthDomain string
}

func loadCustomerAuthConfig(getenv func(string) string) (customerAuthConfig, error) {
	c := customerAuthConfig{Environment: getenv("AUTODATA_ENV"), Mode: getenv("AUTODATA_AUTH_MODE"), Origin: getenv("AUTODATA_PUBLIC_ORIGIN"), ProjectID: getenv("AUTODATA_FIREBASE_PROJECT_ID"), APIKey: getenv("AUTODATA_FIREBASE_WEB_API_KEY"), AppID: getenv("AUTODATA_FIREBASE_WEB_APP_ID"), AuthDomain: getenv("AUTODATA_FIREBASE_AUTH_DOMAIN")}
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
	if c.Environment == "production" && c.Origin != "https://cars.tk" {
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
	return c, nil
}
