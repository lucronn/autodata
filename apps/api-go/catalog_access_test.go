package main

import (
	"context"
	"errors"
	"net/http/httptest"
	"strings"
	"testing"
)

const paidTestConfiguration = "33333333-3333-4333-8333-333333333333"
const paidTestVehicle = "44444444-4444-4444-8444-444444444444"

type paidScopeCatalog struct {
	CatalogStore
	configuration CatalogConfiguration
	err           error
	calls         int
}

func (c *paidScopeCatalog) ConfigurationByVehicle(context.Context, Principal, string) (CatalogConfiguration, error) {
	c.calls++
	return c.configuration, c.err
}

type paidGrantClient struct {
	calls                               int
	err                                 error
	account, org, configuration, region string
}

func (c *paidGrantClient) Do(context.Context, string, []byte, string) (int, []byte, error) {
	panic("unexpected generic commerce call")
}
func (c *paidGrantClient) CheckVehicleGrant(_ context.Context, a, o, configuration, region string) (VehicleGrant, error) {
	c.calls++
	c.account, c.org, c.configuration, c.region = a, o, configuration, region
	return VehicleGrant{ConfigurationID: configuration, Region: region}, c.err
}

func TestPaidCatalogExactScopeBeforeGrant(t *testing.T) {
	p := Principal{CustomerAccountID: "11111111-1111-4111-8111-111111111111", OrganizationID: "22222222-2222-4222-8222-222222222222"}
	for _, tc := range []struct {
		name, input, region string
		config              CatalogConfiguration
		want                error
		grants              int
	}{
		{"exact", paidTestConfiguration, "", CatalogConfiguration{ID: paidTestConfiguration, VehicleID: paidTestVehicle, Region: "CA"}, nil, 1},
		{"base", paidTestVehicle, "", CatalogConfiguration{ID: paidTestConfiguration, VehicleID: paidTestVehicle, Region: "CA"}, ErrCatalogNotFound, 0},
		{"region", paidTestConfiguration, "US", CatalogConfiguration{ID: paidTestConfiguration, Region: "CA"}, ErrCatalogNotFound, 0},
		{"invalid", "wrong", "", CatalogConfiguration{}, ErrCatalogNotFound, 0},
		{"missingregion", paidTestConfiguration, "", CatalogConfiguration{ID: paidTestConfiguration}, ErrCatalogNotFound, 0},
	} {
		t.Run(tc.name, func(t *testing.T) {
			c := &paidScopeCatalog{configuration: tc.config}
			g := &paidGrantClient{}
			s := &Server{catalog: c, commerceClient: g}
			got, err := s.resolvePaidCatalogScope(context.Background(), p, tc.input, tc.region)
			if !errors.Is(err, tc.want) || g.calls != tc.grants {
				t.Fatalf("scope=%+v err=%v grants=%d", got, err, g.calls)
			}
			if tc.grants > 0 && (g.account != p.CustomerAccountID || g.org != p.OrganizationID || g.configuration != paidTestConfiguration || g.region != "CA") {
				t.Fatal("untrusted or defaulted grant scope")
			}
		})
	}
}
func TestPaidCatalogGrantErrorsAreSafe(t *testing.T) {
	for _, tc := range []struct {
		err    error
		status int
		code   string
	}{{ErrVehicleGrantRequired, 403, "ENTITLEMENT_REQUIRED"}, {ErrVehicleGrantRevoked, 403, "ENTITLEMENT_REVOKED"}, {ErrVehicleGrantUnavailable, 503, "CATALOG_UNAVAILABLE"}, {ErrCatalogNotFound, 404, "CATALOG_NOT_FOUND"}, {ErrCatalogWithdrawn, 410, "CATALOG_WITHDRAWN"}, {errors.New("private provider detail"), 503, "CATALOG_UNAVAILABLE"}} {
		t.Run(tc.code, func(t *testing.T) {
			w := httptest.NewRecorder()
			s := &Server{}
			s.writePaidCatalogError(w, httptest.NewRequest("GET", "/v1/catalog/images/private-token", nil), tc.err)
			if w.Code != tc.status || w.Header().Get("Cache-Control") != "private, no-store" {
				t.Fatal(w.Code, w.Header())
			}
			if !strings.Contains(w.Body.String(), tc.code) || strings.Contains(w.Body.String(), "private provider") {
				t.Fatal(w.Body.String())
			}
		})
	}
}
