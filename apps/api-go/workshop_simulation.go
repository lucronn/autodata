package main

import "net/http"

const workshopSimulationMode = "simulation"

func (s *Server) workshopSimulationOwner(r *http.Request) (Principal, bool) {
	if !s.workshopSimulation || s.customerAuth == nil {
		return Principal{}, false
	}
	p, err := s.customerAuth.Authenticate(r)
	if err != nil || !commerceUUID(p.CustomerAccountID) || !commerceUUID(p.OrganizationID) {
		return Principal{}, false
	}
	return p, true
}

func (s *Server) workshopQuoteInput(configurationID, region string, p Principal) map[string]any {
	input := map[string]any{"configuration_id": configurationID, "region": region}
	if s.workshopSimulation && commerceUUID(p.CustomerAccountID) && commerceUUID(p.OrganizationID) {
		input["customer_account_id"], input["organization_id"] = p.CustomerAccountID, p.OrganizationID
	}
	return input
}
