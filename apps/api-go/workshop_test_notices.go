package main

import (
	"html/template"
	"net/http"
	"strings"
)

type workshopTestNotice struct{ Title, First, Second string }

var workshopTestNotices = map[string]workshopTestNotice{
	"terms":   {"Test participation", "This restricted Workshop environment uses Stripe TEST mode. Use test card details only. The displayed USD20 is simulated; no actual payment or tax is collected.", "Access created by a settled test order belongs to this isolated test environment. Test access and test data may be reset or revoked. This demo makes no production purchase or permanent-access promise. Repair information still requires the normal source permissions."},
	"privacy": {"Test data and privacy", "Google/Firebase sign-in identifies your tester account. Workshop stores account/session identifiers, vehicle selections and test order/access records. Stripe handles test checkout details; the Workshop backend receives test payment events and identifiers. Hosting and service diagnostics may also record requests.", "Use test payment details and avoid entering sensitive personal information. Test mode does not make your Google identity anonymous. This page describes the test flow; it does not promise a retention period or replace a production privacy policy."},
	"refund":  {"Test refunds and access", "Stripe TEST payments move no real money. A test refund exercises the refund and access-revocation flow; there is no real payment to reimburse.", "Ask the demo maintainer to investigate a failed test order or exercise a test refund. A completed full test refund can revoke the related test access. This notice does not establish a production refund policy."},
	"contact": {"Demo help and feedback", "Contact the AutoData maintainer through the linked demo issue to report a problem or request a test refund. Include a short description and the time of the test.", "The linked GitHub issue is public. Do not post payment details, passwords, access tokens, personal account details or licensed repair content. This is a test feedback channel with no promised response time."},
}

var workshopSimulationNotices = map[string]workshopTestNotice{
	"terms":   {"Simulated purchase terms", "The Workshop simulates the payment step. No payment details are requested and no money is charged.", "Your test access belongs to the selected vehicle and your tester account. The same Workshop Library and article reader open the authorized data."},
	"privacy": {"Simulated purchase privacy", "The normal Google sign-in identifies your tester account. Workshop records your selected vehicle and simulated purchase to give you access.", "The simulated checkout collects no card details."},
	"refund":  {"Simulated purchases and access", "A simulated purchase has no payment to refund.", "The AutoData maintainer can remove access granted by a simulated purchase."},
	"contact": {"Workshop test feedback", "Contact the AutoData maintainer through the linked issue to report a problem. Include the vehicle selection and time of the test.", "The issue is public. Keep account details, tokens and licensed repair content private."},
}

var workshopTestNoticeTemplate = template.Must(template.New("test-notice").Parse(`<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>{{.Title}} | Workshop TEST</title></head>
<body><header><p><strong>Workshop TEST — No real money is charged.</strong></p></header>
<main><h1>{{.Title}}</h1><p>{{.First}}</p><p>{{.Second}}</p><p><a href="https://github.com/lucronn/autodata/issues/398" rel="noreferrer">Contact the AutoData demo maintainer on GitHub</a></p></main>
<footer><p><a href="{{.ReturnURL}}">Return to Workshop TEST</a></p><nav aria-label="Test notices"><ul><li><a href="/workshop/test-notices/terms">Test participation</a></li><li><a href="/workshop/test-notices/privacy">Test data and privacy</a></li><li><a href="/workshop/test-notices/refund">Test refunds and access</a></li><li><a href="/workshop/test-notices/contact">Demo help and feedback</a></li></ul></nav></footer></body></html>`))

func (s *Server) workshopTestNotice(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Cache-Control", "no-store")
	w.Header().Set("X-Content-Type-Options", "nosniff")
	w.Header().Set("Content-Security-Policy", "default-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'none'")
	name := strings.TrimPrefix(r.URL.Path, "/workshop/test-notices/")
	notice, ok := workshopTestNotices[name]
	returnURL := "/workshop/?demo=1"
	if s.workshopSimulation {
		notice, ok = workshopSimulationNotices[name]
		returnURL = "/workshop/"
	}
	if (!s.workshopTestCheckout && !s.workshopSimulation) || !ok || r.URL.RawPath != "" || r.URL.RawQuery != "" || r.URL.ForceQuery {
		http.NotFound(w, r)
		return
	}
	if r.Method != http.MethodGet && r.Method != http.MethodHead {
		w.Header().Set("Allow", "GET, HEAD")
		http.Error(w, "method not allowed", 405)
		return
	}
	w.Header().Set("Content-Type", "text/html; charset=utf-8")
	if r.Method == http.MethodHead {
		w.WriteHeader(http.StatusOK)
		return
	}
	_ = workshopTestNoticeTemplate.Execute(w, struct {
		workshopTestNotice
		ReturnURL string
	}{notice, returnURL})
}
