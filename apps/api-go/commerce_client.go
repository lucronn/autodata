package main

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"strings"
	"time"
)

type HTTPCommerceClient struct {
	baseURL, token string
	client         *http.Client
}

func NewHTTPCommerceClient(baseURL, token string) (*HTTPCommerceClient, error) {
	u, err := url.Parse(baseURL)
	if err != nil || u == nil || (u.Scheme != "http" && u.Scheme != "https") || u.Hostname() == "" || u.User != nil || (u.Path != "" && u.Path != "/") || u.RawQuery != "" || u.ForceQuery || u.Fragment != "" || u.Opaque != "" || strings.TrimSpace(token) == "" || strings.ContainsAny(token, "\r\n") {
		return nil, fmt.Errorf("invalid commerce configuration")
	}
	return &HTTPCommerceClient{baseURL: strings.TrimSuffix(u.String(), "/"), token: token, client: &http.Client{Timeout: 20 * time.Second, CheckRedirect: func(*http.Request, []*http.Request) error { return http.ErrUseLastResponse }}}, nil
}
func commerceTimeout(op string) time.Duration {
	switch op {
	case "quote", "library", "grants/check":
		return 2 * time.Second
	default:
		return 20 * time.Second
	}
}
func (c *HTTPCommerceClient) Do(ctx context.Context, operation string, body []byte, signature string) (int, []byte, error) {
	switch operation {
	case "quote", "checkouts", "orders/status", "library", "grants/check", "stripe/webhook":
	default:
		return 0, nil, fmt.Errorf("invalid commerce operation")
	}
	if c == nil || c.client == nil || c.token == "" || len(body) > 1<<20 || len(signature) > 4096 {
		return 0, nil, ErrVehicleGrantUnavailable
	}
	ctx, cancel := context.WithTimeout(ctx, commerceTimeout(operation))
	defer cancel()
	r, err := http.NewRequestWithContext(ctx, http.MethodPost, c.baseURL+"/internal/commerce/"+operation, bytes.NewReader(body))
	if err != nil {
		return 0, nil, ErrVehicleGrantUnavailable
	}
	r.Header.Set("X-Autodata-Internal-Token", c.token)
	r.Header.Set("Accept", "application/json")
	r.Header.Set("Content-Type", "application/json")
	if operation == "stripe/webhook" {
		r.Header.Set("Stripe-Signature", signature)
	}
	response, err := c.client.Do(r)
	if err != nil {
		return 0, nil, ErrVehicleGrantUnavailable
	}
	defer response.Body.Close()
	b, err := io.ReadAll(io.LimitReader(response.Body, maxCommerceResponseBytes+1))
	if err != nil || len(b) > maxCommerceResponseBytes {
		return 0, nil, ErrVehicleGrantUnavailable
	}
	return response.StatusCode, b, nil
}
func (c *HTTPCommerceClient) CheckVehicleGrant(ctx context.Context, accountID, configurationID, region string) (VehicleGrant, error) {
	b, _ := json.Marshal(map[string]string{"customer_account_id": accountID, "configuration_id": configurationID, "region": region})
	status, body, err := c.Do(ctx, "grants/check", b, "")
	if err != nil {
		return VehicleGrant{}, ErrVehicleGrantUnavailable
	}
	if status == 403 {
		switch commerceErrorCode(body) {
		case "ENTITLEMENT_REQUIRED":
			return VehicleGrant{}, ErrVehicleGrantRequired
		case "ENTITLEMENT_REVOKED":
			return VehicleGrant{}, ErrVehicleGrantRevoked
		}
	}
	var grant VehicleGrant
	if status != 200 || json.Unmarshal(body, &grant) != nil || !commerceUUID(grant.EntitlementID) || !commerceUUID(grant.OrderID) || grant.ConfigurationID != configurationID || grant.Region != region || !commerceScopeValid(configurationID, region) {
		return VehicleGrant{}, ErrVehicleGrantUnavailable
	}
	return grant, nil
}

// Enabled commerce requires its private authenticated authority; disabled mode
// retains the routes with safe 503 responses and performs no payment operation.
func configuredCommerceClient(getenv func(string) string) (CommerceClient, error) {
	mode := getenv("AUTODATA_COMMERCE_MODE")
	switch mode {
	case "", "disabled":
		return nil, nil
	case "stripe_test", "stripe_live":
		return NewHTTPCommerceClient(getenv("AUTODATA_INGESTION_URL"), getenv("AUTODATA_INGESTION_INTERNAL_TOKEN"))
	default:
		return nil, fmt.Errorf("invalid commerce mode")
	}
}
