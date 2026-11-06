package main

import (
	"context"
	"net/http"
	"os"
	"time"

	firebase "firebase.google.com/go/v4"
	"firebase.google.com/go/v4/auth"
	"golang.org/x/oauth2"
	"golang.org/x/oauth2/google"
	"google.golang.org/api/option"
)

type firebaseCustomerVerifier struct {
	client    *auth.Client
	projectID string
	now       func() time.Time
}

func newFirebaseCustomerVerifier(ctx context.Context, c customerAuthConfig) (CustomerIdentityVerifier, error) {
	if os.Getenv("FIREBASE_AUTH_EMULATOR_HOST") != "" {
		return nil, ErrCustomerDependency
	}
	// ADC token sources retain this context for the verifier's lifetime.
	// Bound refresh HTTP independently of the short-lived startup context.
	credentialCtx := context.WithoutCancel(ctx)
	refreshClient := &http.Client{}
	if injected, ok := ctx.Value(oauth2.HTTPClient).(*http.Client); ok && injected != nil {
		copied := *injected
		refreshClient = &copied
	}
	refreshClient.Timeout = 2 * time.Second
	credentialCtx = context.WithValue(credentialCtx, oauth2.HTTPClient, refreshClient)
	credentials, err := google.FindDefaultCredentials(credentialCtx, "https://www.googleapis.com/auth/cloud-platform", "https://www.googleapis.com/auth/identitytoolkit")
	if err != nil || credentials.TokenSource == nil {
		return nil, ErrCustomerDependency
	}
	app, err := firebase.NewApp(ctx, &firebase.Config{ProjectID: c.ProjectID}, option.WithCredentials(credentials))
	if err != nil {
		return nil, ErrCustomerDependency
	}
	client, err := app.Auth(ctx)
	if err != nil {
		return nil, ErrCustomerDependency
	}
	return &firebaseCustomerVerifier{client: client, projectID: c.ProjectID}, nil
}
func firebaseIdentityError(err error) error {
	if auth.IsIDTokenInvalid(err) || auth.IsIDTokenExpired(err) || auth.IsIDTokenRevoked(err) || auth.IsUserDisabled(err) || auth.IsUserNotFound(err) {
		return ErrUnauthenticated
	}
	return ErrCustomerDependency
}
func (v *firebaseCustomerVerifier) VerifyLogin(ctx context.Context, raw string) (VerifiedCustomerIdentity, error) {
	if v == nil || v.client == nil {
		return VerifiedCustomerIdentity{}, ErrCustomerDependency
	}
	ctx, cancel := context.WithTimeout(ctx, 2*time.Second)
	defer cancel()
	token, err := v.client.VerifyIDTokenAndCheckRevoked(ctx, raw)
	if err != nil {
		return VerifiedCustomerIdentity{}, firebaseIdentityError(err)
	}
	now := time.Now()
	if v.now != nil {
		now = v.now()
	}
	stamp := now.Unix()
	if token.UID == "" || token.Audience != v.projectID || token.Issuer != "https://securetoken.google.com/"+v.projectID || token.Firebase.SignInProvider != "google.com" || token.Firebase.Tenant != "" || token.AuthTime <= 0 || token.IssuedAt <= 0 || token.Expires <= stamp || token.AuthTime < stamp-300 || token.IssuedAt < stamp-300 || token.AuthTime > stamp+60 || token.IssuedAt > stamp+60 {
		return VerifiedCustomerIdentity{}, ErrUnauthenticated
	}
	// The SDK checks iat revocation. Check original authentication time too.
	if err = v.CheckUser(ctx, v.projectID, token.UID, token.AuthTime); err != nil {
		return VerifiedCustomerIdentity{}, err
	}
	return VerifiedCustomerIdentity{ProjectID: v.projectID, UID: token.UID, AuthTime: token.AuthTime, IssuedAt: token.IssuedAt, Expires: token.Expires}, nil
}
func (v *firebaseCustomerVerifier) CheckUser(ctx context.Context, projectID, uid string, authTime int64) error {
	if v == nil || v.client == nil {
		return ErrCustomerDependency
	}
	if projectID != v.projectID || uid == "" || authTime <= 0 {
		return ErrUnauthenticated
	}
	ctx, cancel := context.WithTimeout(ctx, 2*time.Second)
	defer cancel()
	user, err := v.client.GetUser(ctx, uid)
	if err != nil {
		return firebaseIdentityError(err)
	}
	if user.UID != uid || user.Disabled || authTime*1000 < user.TokensValidAfterMillis {
		return ErrUnauthenticated
	}
	return nil
}
