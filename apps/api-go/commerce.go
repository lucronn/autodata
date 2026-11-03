package main

import (
	"context"
	"encoding/json"
	"errors"
	"net/url"
	"strings"
	"time"
	"unicode"
)

const maxCommerceResponseBytes = 1 << 20

// CommerceClient delegates to the single private payment/grant authority.
// The body is constructed by the API, never copied from browser JSON.
type CommerceClient interface {
	Do(context.Context, string, []byte, string) (int, []byte, error)
}

type VehicleGrant struct {
	EntitlementID   string `json:"entitlement_id"`
	OrderID         string `json:"order_id"`
	ConfigurationID string `json:"configuration_id"`
	Region          string `json:"region"`
}

var (
	ErrVehicleGrantRequired    = errors.New("vehicle grant required")
	ErrVehicleGrantRevoked     = errors.New("vehicle grant revoked")
	ErrVehicleGrantUnavailable = errors.New("vehicle grant unavailable")
)

type VehicleGrantChecker interface {
	CheckVehicleGrant(context.Context, string, string, string) (VehicleGrant, error)
}

type commerceScope struct {
	ConfigurationID string `json:"configuration_id"`
	Region          string `json:"region"`
}
type commerceQuote struct {
	Version              string `json:"version"`
	ProductKey           string `json:"product_key"`
	ConfigurationID      string `json:"configuration_id"`
	Region               string `json:"region"`
	ConfigurationLabel   string `json:"configuration_label"`
	AmountMinor          int64  `json:"amount_minor"`
	Currency             string `json:"currency"`
	PurchaseTermsVersion string `json:"purchase_terms_version"`
	Purchasable          bool   `json:"purchasable"`
}
type commerceCheckout struct {
	Version           string `json:"version"`
	State             string `json:"state"`
	OrderID           string `json:"order_id"`
	ConfigurationID   string `json:"configuration_id"`
	Region            string `json:"region"`
	CheckoutURL       string `json:"checkout_url,omitempty"`
	ProviderExpiresAt string `json:"provider_expires_at,omitempty"`
	LibraryItemID     string `json:"library_item_id,omitempty"`
}
type commerceOrder struct {
	Version          string `json:"version"`
	OrderID          string `json:"order_id"`
	ConfigurationID  string `json:"configuration_id"`
	Region           string `json:"region"`
	State            string `json:"state"`
	RetryDisposition string `json:"retry_disposition"`
}
type commerceLibraryItem struct {
	LibraryItemID    string  `json:"library_item_id"`
	ConfigurationID  string  `json:"configuration_id"`
	Region           string  `json:"region"`
	Label            string  `json:"label"`
	AccessState      string  `json:"access_state"`
	GrantedAt        *string `json:"granted_at"`
	RevokedAt        string  `json:"revoked_at,omitempty"`
	DatasetID        string  `json:"dataset_id,omitempty"`
	ContentErrorCode string  `json:"content_error_code,omitempty"`
}
type commerceLibrary struct {
	Version    string                `json:"version"`
	Items      []commerceLibraryItem `json:"items"`
	NextCursor *string               `json:"next_cursor"`
}
type commerceWebhook struct {
	Status string `json:"status"`
}

func commerceUUID(v string) bool {
	return v == strings.TrimSpace(v) && v == strings.ToLower(v) && validUUID(v)
}
func commerceRegion(v string) bool {
	return len(v) == 2 && v[0] >= 'A' && v[0] <= 'Z' && v[1] >= 'A' && v[1] <= 'Z'
}
func commerceTime(v string) bool {
	parsed, err := time.Parse(time.RFC3339, v)
	_, offset := parsed.Zone()
	return err == nil && offset == 0 && (strings.HasSuffix(v, "Z") || strings.HasSuffix(v, "+00:00"))
}
func commerceHostedURL(v string) bool {
	if strings.IndexFunc(v, func(r rune) bool { return unicode.IsSpace(r) || unicode.IsControl(r) }) >= 0 {
		return false
	}
	u, e := url.Parse(v)
	return e == nil && u.Scheme == "https" && u.Host == "checkout.stripe.com" && u.User == nil && strings.HasPrefix(u.Path, "/c/pay/")
}
func commerceScopeValid(id, region string) bool { return commerceUUID(id) && commerceRegion(region) }
func commerceErrorCode(body []byte) string {
	var v struct {
		Error struct {
			Code string `json:"code"`
		} `json:"error"`
	}
	if json.Unmarshal(body, &v) != nil {
		return ""
	}
	return v.Error.Code
}

// Project private responses into bounded public DTOs. Unknown private fields
// are never serialized, and a malformed success cannot become a public success.
func commercePublicResult(operation string, status int, body []byte, input map[string]any) (any, bool) {
	if len(body) > maxCommerceResponseBytes {
		return nil, false
	}
	scopeMatches := func(id, region string) bool {
		if !commerceScopeValid(id, region) {
			return false
		}
		if wanted, ok := input["configuration_id"].(string); ok && wanted != id {
			return false
		}
		if wanted, ok := input["region"].(string); ok && wanted != region {
			return false
		}
		return true
	}
	switch operation {
	case "quote":
		var v commerceQuote
		if status != 200 || json.Unmarshal(body, &v) != nil {
			return nil, false
		}
		return v, v.Version == "v1" && v.ProductKey == "workshop-configuration-v1" && scopeMatches(v.ConfigurationID, v.Region) && len(v.ConfigurationLabel) > 0 && len(v.ConfigurationLabel) <= 1024 && v.AmountMinor == 2000 && v.Currency == "USD" && v.PurchaseTermsVersion == "workshop-v1" && v.Purchasable
	case "checkouts":
		var v commerceCheckout
		if json.Unmarshal(body, &v) != nil || v.Version != "v1" || !commerceUUID(v.OrderID) || !scopeMatches(v.ConfigurationID, v.Region) {
			return nil, false
		}
		switch v.State {
		case "checkout":
			return v, (status == 200 || status == 201) && commerceHostedURL(v.CheckoutURL) && commerceTime(v.ProviderExpiresAt) && v.LibraryItemID == ""
		case "processing":
			return v, status == 202 && v.CheckoutURL == "" && v.ProviderExpiresAt == "" && v.LibraryItemID == ""
		case "owned":
			return v, status == 200 && commerceUUID(v.LibraryItemID) && v.LibraryItemID == v.OrderID && v.CheckoutURL == "" && v.ProviderExpiresAt == ""
		}
		return nil, false
	case "orders/status":
		var v commerceOrder
		if status != 200 || json.Unmarshal(body, &v) != nil || v.Version != "v1" || v.OrderID != input["order_id"] || !commerceUUID(v.OrderID) || !scopeMatches(v.ConfigurationID, v.Region) {
			return nil, false
		}
		switch v.State {
		case "expired", "canceled":
			return v, v.RetryDisposition == "new_key"
		case "creating", "open", "processing", "paid", "reconciliation_required", "revoked":
			return v, v.RetryDisposition == "do_not_repay"
		}
		return nil, false
	case "library":
		var v commerceLibrary
		if status != 200 || json.Unmarshal(body, &v) != nil || v.Version != "v1" || v.Items == nil || len(v.Items) > input["limit"].(int) || (v.NextCursor != nil && len(*v.NextCursor) > 2048) {
			return nil, false
		}
		var fields struct {
			NextCursor json.RawMessage              `json:"next_cursor"`
			Items      []map[string]json.RawMessage `json:"items"`
		}
		if json.Unmarshal(body, &fields) != nil || len(fields.NextCursor) == 0 {
			return nil, false
		}
		for index, item := range v.Items {
			if len(fields.Items[index]["granted_at"]) == 0 {
				return nil, false
			}
			if !commerceUUID(item.LibraryItemID) || !commerceScopeValid(item.ConfigurationID, item.Region) || len(item.Label) > 1024 || (item.GrantedAt == nil && item.AccessState != "revoked") || (item.GrantedAt != nil && !commerceTime(*item.GrantedAt)) || (item.RevokedAt != "" && !commerceTime(item.RevokedAt)) || (item.DatasetID != "" && !commerceUUID(item.DatasetID)) {
				return nil, false
			}
			switch item.AccessState {
			case "paid", "preparing", "viewable", "revoked":
			default:
				return nil, false
			}
			switch item.ContentErrorCode {
			case "", "CATALOG_PREPARATION_UNAVAILABLE", "CATALOG_PREPARATION_REVIEW", "CATALOG_SOURCE_UNAVAILABLE":
			default:
				return nil, false
			}
		}
		return v, true
	case "stripe/webhook":
		var v commerceWebhook
		if status != 200 || json.Unmarshal(body, &v) != nil {
			return nil, false
		}
		switch v.Status {
		case "accepted", "pending", "quarantined", "ignored":
			return v, true
		}
	}
	return nil, false
}
