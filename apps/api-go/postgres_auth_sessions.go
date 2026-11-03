package main

import (
	"context"
	"errors"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
)

type postgresCustomerSessions struct{ pool *pgxpool.Pool }

func (s *postgresCustomerSessions) CheckSchema(ctx context.Context) error {
	if s == nil || s.pool == nil {
		return ErrCustomerDependency
	}
	var migrated bool
	if err := s.pool.QueryRow(ctx, "SELECT EXISTS(SELECT 1 FROM schema_migrations WHERE version='039_production_identity_sessions')").Scan(&migrated); err != nil || !migrated {
		return ErrCustomerDependency
	}
	rows, err := s.pool.Query(ctx, `SELECT a.customer_account_id,a.firebase_project_id,a.firebase_uid,a.personal_organization_id,a.status,s.session_token_hash,s.firebase_auth_time,s.created_at,s.expires_at,s.revoked_at FROM customer_accounts a LEFT JOIN auth_sessions s USING(customer_account_id) LIMIT 0`)
	if err != nil {
		return ErrCustomerDependency
	}
	rows.Close()
	return nil
}
func (s *postgresCustomerSessions) Rotate(ctx context.Context, identity VerifiedCustomerIdentity, hash, oldHash []byte, created, expires time.Time) (customerSession, error) {
	if s == nil || s.pool == nil {
		return customerSession{}, ErrCustomerDependency
	}
	if identity.ProjectID == "" || identity.UID == "" || identity.AuthTime <= 0 || len(hash) != 32 || !expires.After(created) || expires.Sub(created) > customerSessionLifetime {
		return customerSession{}, ErrUnauthenticated
	}
	tx, err := s.pool.BeginTx(ctx, pgx.TxOptions{})
	if err != nil {
		return customerSession{}, ErrCustomerDependency
	}
	defer tx.Rollback(ctx)
	var result customerSession
	var status string
	err = tx.QueryRow(ctx, `INSERT INTO customer_accounts(firebase_project_id,firebase_uid) VALUES($1,$2) ON CONFLICT(firebase_project_id,firebase_uid) DO UPDATE SET firebase_uid=EXCLUDED.firebase_uid RETURNING customer_account_id::text,personal_organization_id::text,status`, identity.ProjectID, identity.UID).Scan(&result.AccountID, &result.OrganizationID, &status)
	if err != nil {
		return customerSession{}, ErrCustomerDependency
	}
	if status != "active" {
		return customerSession{}, ErrCustomerBlocked
	}
	if len(oldHash) == 32 {
		if _, err = tx.Exec(ctx, `UPDATE auth_sessions SET revoked_at=$2 WHERE session_token_hash=$1 AND revoked_at IS NULL AND expires_at>$2`, oldHash, created); err != nil {
			return customerSession{}, ErrCustomerDependency
		}
	}
	_, err = tx.Exec(ctx, `INSERT INTO auth_sessions(session_token_hash,customer_account_id,firebase_auth_time,created_at,expires_at) VALUES($1,$2::uuid,$3,$4,$5)`, hash, result.AccountID, identity.AuthTime, created, expires)
	if err != nil {
		return customerSession{}, ErrCustomerDependency
	}
	if err = tx.Commit(ctx); err != nil {
		return customerSession{}, ErrCustomerDependency
	}
	result.ProjectID = identity.ProjectID
	result.UID = identity.UID
	result.AuthTime = identity.AuthTime
	result.ExpiresAt = expires
	return result, nil
}
func (s *postgresCustomerSessions) Lookup(ctx context.Context, hash []byte, now time.Time) (customerSession, error) {
	if s == nil || s.pool == nil {
		return customerSession{}, ErrCustomerDependency
	}
	if len(hash) != 32 {
		return customerSession{}, ErrUnauthenticated
	}
	var result customerSession
	var status string
	err := s.pool.QueryRow(ctx, `SELECT a.customer_account_id::text,a.personal_organization_id::text,a.firebase_project_id,a.firebase_uid,a.status,s.firebase_auth_time,s.expires_at FROM auth_sessions s JOIN customer_accounts a USING(customer_account_id) WHERE s.session_token_hash=$1 AND s.revoked_at IS NULL AND s.expires_at>$2`, hash, now).Scan(&result.AccountID, &result.OrganizationID, &result.ProjectID, &result.UID, &status, &result.AuthTime, &result.ExpiresAt)
	if errors.Is(err, pgx.ErrNoRows) {
		return customerSession{}, ErrUnauthenticated
	}
	if err != nil {
		return customerSession{}, ErrCustomerDependency
	}
	if status != "active" {
		return customerSession{}, ErrCustomerBlocked
	}
	return result, nil
}
func (s *postgresCustomerSessions) Revoke(ctx context.Context, hash []byte, now time.Time) error {
	if s == nil || s.pool == nil {
		return ErrCustomerDependency
	}
	if _, err := s.pool.Exec(ctx, `UPDATE auth_sessions SET revoked_at=COALESCE(revoked_at,$2) WHERE session_token_hash=$1`, hash, now); err != nil {
		return ErrCustomerDependency
	}
	return nil
}
