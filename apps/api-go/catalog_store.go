package main

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"sort"
	"strconv"
	"strings"
	"sync"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
)

var (
	ErrCatalogNotFound = errors.New("catalog resource not found")
	ErrCatalogInvalid  = errors.New("catalog request is invalid")
)

// CatalogStore is the provider-neutral read boundary used by the public API.
// Implementations own hydration and persistence; handlers never see provider
// response objects or database rows.
type CatalogStore interface {
	Years(context.Context, Principal) ([]CatalogYear, error)
	Makes(context.Context, Principal, int, string) ([]CatalogMake, error)
	Models(context.Context, Principal, int, string, string) ([]CatalogModel, error)
	Configurations(context.Context, Principal, int, string, string, string) ([]CatalogConfiguration, error)
	CatalogScopeComplete(context.Context, Principal, string, int, string, string, string) (bool, error)
	CatalogArticleProgress(context.Context, Principal, string) (*CatalogArticleProgress, error)
	ConfigurationByVehicle(context.Context, Principal, string) (CatalogConfiguration, error)
	Articles(context.Context, Principal, string) ([]CatalogArticle, error)
	Article(context.Context, Principal, string, string) (CatalogArticle, error)
	ArticleSource(context.Context, Principal, string, string) (CatalogSourceContent, error)
}

type CatalogYear struct {
	Year int `json:"year"`
}

type CatalogMake struct {
	ID   string `json:"id"`
	Name string `json:"name"`
}

type CatalogModel struct {
	ID   string `json:"id"`
	Name string `json:"name"`
}

type CatalogConfiguration struct {
	ID        string `json:"id"`
	VehicleID string `json:"vehicle_id"`
	Year      int    `json:"year"`
	Make      string `json:"make"`
	Model     string `json:"model"`
	Region    string `json:"region,omitempty"`
	Trim      string `json:"trim,omitempty"`
	Engine    string `json:"engine,omitempty"`
	Complete  bool   `json:"complete"`
}

type CatalogProvenance struct {
	ID      string `json:"id"`
	Version string `json:"version,omitempty"`
}

type CatalogStep struct {
	Number       int      `json:"number"`
	Heading      string   `json:"heading,omitempty"`
	Instructions []string `json:"instructions"`
	ImageIDs     []string `json:"image_ids,omitempty"`
}

type CatalogDocument struct {
	SchemaVersion        int                    `json:"schema_version"`
	NormalizationVersion string                 `json:"normalization_version"`
	Blocks               []CatalogDocumentBlock `json:"blocks"`
}

type CatalogDocumentBlock struct {
	BlockID           string   `json:"block_id,omitempty"`
	SourceOrder       int      `json:"source_order,omitempty"`
	Type              string   `json:"type"`
	Level             int      `json:"level,omitempty"`
	Number            int      `json:"number,omitempty"`
	Text              string   `json:"text,omitempty"`
	Label             string   `json:"label,omitempty"`
	Href              string   `json:"href,omitempty"`
	Columns           []string `json:"columns,omitempty"`
	Rows              [][]any  `json:"rows,omitempty"`
	Items             []string `json:"items,omitempty"`
	AssetID           string   `json:"asset_id,omitempty"`
	ImageID           string   `json:"image_id,omitempty"`
	Alt               string   `json:"alt,omitempty"`
	Status            string   `json:"status,omitempty"`
	UnavailableReason string   `json:"unavailable_reason,omitempty"`
	EvidenceIDs       []string `json:"evidence_ids,omitempty"`
	SourceLocator     string   `json:"source_locator,omitempty"`
}

type CatalogArticle struct {
	ID                  string               `json:"id"`
	VehicleID           string               `json:"vehicle_id"`
	Title               string               `json:"title"`
	Kind                string               `json:"kind,omitempty"`
	Component           string               `json:"component,omitempty"`
	ContentStatus       string               `json:"content_status"`
	Complete            bool                 `json:"complete"`
	Body                string               `json:"body,omitempty"`
	Steps               []CatalogStep        `json:"steps,omitempty"`
	Document            *CatalogDocument     `json:"document,omitempty"`
	Images              []CatalogImage       `json:"images,omitempty"`
	Provenance          []CatalogProvenance  `json:"provenance,omitempty"`
	SourceReview        *CatalogSourceReview `json:"source_review,omitempty"`
	SourceOriginal      json.RawMessage      `json:"-"`
	sourceArticleID     string
	sourceSnapshotID    string
	sourceVersion       string
	sourceContentSHA256 string
	sourceURI           string
	sourceFormat        string
	sourceAvailable     bool
}

// CatalogSourceReview is safe metadata for the immutable source copy. The
// source URL is always an AutoData route; the provider URI and raw payload
// stay behind ArticleSource and the source-review renderer.
type CatalogSourceReview struct {
	Available     bool   `json:"available"`
	SnapshotID    string `json:"snapshot_id,omitempty"`
	Version       string `json:"version,omitempty"`
	ContentSHA256 string `json:"content_sha256,omitempty"`
	Format        string `json:"format,omitempty"`
	URL           string `json:"url,omitempty"`
}

type CatalogSourceContent struct {
	SnapshotID    string
	Version       string
	ContentSHA256 string
	SourceURI     string
	Original      json.RawMessage
}

type CatalogArticleProgress struct {
	Status           string `json:"status"`
	Phase            string `json:"phase"`
	Processed        int    `json:"processed"`
	Total            int    `json:"total"`
	Percent          int    `json:"percent"`
	CurrentArticleID string `json:"current_article_id,omitempty"`
	CurrentTitle     string `json:"current_title,omitempty"`
	Detail           string `json:"detail,omitempty"`
}

type CatalogImage struct {
	ID         string `json:"id,omitempty"`
	URL        string `json:"url,omitempty"`
	Alt        string `json:"alt,omitempty"`
	StorageKey string `json:"-"`
	MediaType  string `json:"media_type,omitempty"`
	ImageID    string `json:"image_id,omitempty"`
}

// UnmarshalJSON retains the private storage locator from persisted article
// JSON. StorageKey remains excluded from public JSON by its struct tag.
func (image *CatalogImage) UnmarshalJSON(data []byte) error {
	type publicImage CatalogImage
	var decoded struct {
		publicImage
		StorageKey string `json:"storage_key"`
	}
	if err := json.Unmarshal(data, &decoded); err != nil {
		return err
	}
	*image = CatalogImage(decoded.publicImage)
	image.StorageKey = decoded.StorageKey
	return nil
}

type memoryCatalogStore struct {
	mu             sync.RWMutex
	configurations map[string]CatalogConfiguration
	articles       map[string]CatalogArticle
}

func newMemoryCatalogStore() *memoryCatalogStore {
	return &memoryCatalogStore{configurations: map[string]CatalogConfiguration{}, articles: map[string]CatalogArticle{}}
}

func (s *memoryCatalogStore) PutConfiguration(record CatalogConfiguration) {
	s.mu.Lock()
	defer s.mu.Unlock()
	if record.ID == "" {
		record.ID = catalogConfigurationID(record)
	}
	if record.VehicleID == "" {
		record.VehicleID = record.ID
	}
	s.configurations[record.ID] = record
}

func (s *memoryCatalogStore) PutArticle(record CatalogArticle) {
	s.mu.Lock()
	defer s.mu.Unlock()
	if _, exists := s.articles[record.ID]; exists {
		return
	}
	record.Steps = orderedCatalogSteps(record.Steps)
	record.SourceOriginal = append(json.RawMessage(nil), record.SourceOriginal...)
	record.sourceAvailable = len(bytes.TrimSpace(record.SourceOriginal)) > 2
	record.sourceFormat = catalogSourceFormat(record.SourceOriginal)
	if record.sourceSnapshotID == "" && len(record.Provenance) > 0 {
		record.sourceSnapshotID = record.Provenance[0].ID
	}
	if record.sourceVersion == "" && len(record.Provenance) > 0 {
		record.sourceVersion = record.Provenance[0].Version
	}
	record.Provenance = append([]CatalogProvenance(nil), record.Provenance...)
	s.articles[record.ID] = record
}

func (s *memoryCatalogStore) Years(context.Context, Principal) ([]CatalogYear, error) {
	s.mu.RLock()
	defer s.mu.RUnlock()
	years := map[int]bool{}
	for _, record := range s.configurations {
		years[record.Year] = true
	}
	result := make([]CatalogYear, 0, len(years))
	for year := range years {
		result = append(result, CatalogYear{Year: year})
	}
	sort.Slice(result, func(i, j int) bool { return result[i].Year < result[j].Year })
	return result, nil
}

func (s *memoryCatalogStore) Makes(_ context.Context, _ Principal, year int, region string) ([]CatalogMake, error) {
	s.mu.RLock()
	defer s.mu.RUnlock()
	seen := map[string]CatalogMake{}
	for _, record := range s.configurations {
		if record.Year == year && (region == "" || strings.EqualFold(record.Region, region)) {
			name := catalogMakeLabel(record.Make)
			seen[catalogSlug(name)] = CatalogMake{ID: catalogSlug(name), Name: name}
		}
	}
	result := make([]CatalogMake, 0, len(seen))
	for _, makeRecord := range seen {
		result = append(result, makeRecord)
	}
	sort.Slice(result, func(i, j int) bool { return result[i].Name < result[j].Name })
	return result, nil
}

func (s *memoryCatalogStore) Models(_ context.Context, _ Principal, year int, makeName, region string) ([]CatalogModel, error) {
	s.mu.RLock()
	defer s.mu.RUnlock()
	seen := map[string]CatalogModel{}
	for _, record := range s.configurations {
		if record.Year == year && strings.EqualFold(record.Make, makeName) && (region == "" || strings.EqualFold(record.Region, region)) {
			name := catalogLabel(record.Model)
			seen[catalogSlug(name)] = CatalogModel{ID: catalogSlug(name), Name: name}
		}
	}
	result := make([]CatalogModel, 0, len(seen))
	for _, modelRecord := range seen {
		result = append(result, modelRecord)
	}
	sort.Slice(result, func(i, j int) bool { return result[i].Name < result[j].Name })
	return result, nil
}

func (s *memoryCatalogStore) Configurations(_ context.Context, _ Principal, year int, makeName, model, region string) ([]CatalogConfiguration, error) {
	s.mu.RLock()
	defer s.mu.RUnlock()
	result := []CatalogConfiguration{}
	for _, record := range s.configurations {
		if record.Year == year && strings.EqualFold(record.Make, makeName) && strings.EqualFold(record.Model, model) && (region == "" || strings.EqualFold(record.Region, region)) {
			result = append(result, record)
		}
	}
	sort.Slice(result, func(i, j int) bool { return result[i].ID < result[j].ID })
	return result, nil
}

func (s *memoryCatalogStore) CatalogScopeComplete(_ context.Context, _ Principal, scope string, year int, makeName, model, region string) (bool, error) {
	s.mu.RLock()
	defer s.mu.RUnlock()
	for _, record := range s.configurations {
		if record.Year != year || (region != "" && !strings.EqualFold(record.Region, region)) {
			continue
		}
		if scope != "makes" && !strings.EqualFold(record.Make, makeName) {
			continue
		}
		if scope == "configurations" && !strings.EqualFold(record.Model, model) {
			continue
		}
		return true, nil
	}
	return false, nil
}

func (s *memoryCatalogStore) CatalogArticleProgress(context.Context, Principal, string) (*CatalogArticleProgress, error) {
	return nil, nil
}

func (s *memoryCatalogStore) ConfigurationByVehicle(_ context.Context, _ Principal, vehicleID string) (CatalogConfiguration, error) {
	s.mu.RLock()
	defer s.mu.RUnlock()
	for _, record := range s.configurations {
		if record.VehicleID == vehicleID {
			return record, nil
		}
	}
	return CatalogConfiguration{}, ErrCatalogNotFound
}

func (s *memoryCatalogStore) Articles(_ context.Context, _ Principal, vehicleID string) ([]CatalogArticle, error) {
	s.mu.RLock()
	defer s.mu.RUnlock()
	result := []CatalogArticle{}
	for _, record := range s.articles {
		if record.VehicleID == vehicleID {
			result = append(result, publicCatalogArticle(record))
		}
	}
	sort.Slice(result, func(i, j int) bool { return result[i].ID < result[j].ID })
	return result, nil
}

func (s *memoryCatalogStore) Article(_ context.Context, _ Principal, vehicleID, articleID string) (CatalogArticle, error) {
	s.mu.RLock()
	defer s.mu.RUnlock()
	record, ok := s.articles[articleID]
	if !ok || record.VehicleID != vehicleID {
		return CatalogArticle{}, ErrCatalogNotFound
	}
	return publicCatalogArticle(record), nil
}

func (s *memoryCatalogStore) ArticleSource(_ context.Context, _ Principal, vehicleID, articleID string) (CatalogSourceContent, error) {
	s.mu.RLock()
	defer s.mu.RUnlock()
	lookupID := articleID
	if alias, ok := s.articles[articleID]; ok && alias.sourceArticleID != "" {
		lookupID = alias.sourceArticleID
	}
	for _, record := range s.articles {
		if record.VehicleID != vehicleID || (record.ID != lookupID && record.sourceArticleID != lookupID) || !record.sourceAvailable {
			continue
		}
		return CatalogSourceContent{
			SnapshotID: record.sourceSnapshotID, Version: record.sourceVersion,
			ContentSHA256: record.sourceContentSHA256, SourceURI: record.sourceURI,
			Original: cloneCatalogRaw(record.SourceOriginal),
		}, nil
	}
	return CatalogSourceContent{}, ErrCatalogNotFound
}

func publicCatalogArticle(record CatalogArticle) CatalogArticle {
	record.Steps = orderedCatalogSteps(record.Steps)
	if record.Document != nil {
		record.Document.Blocks = append([]CatalogDocumentBlock(nil), record.Document.Blocks...)
	}
	record.SourceOriginal = nil
	return record
}

func orderedCatalogSteps(steps []CatalogStep) []CatalogStep {
	result := append([]CatalogStep(nil), steps...)
	sort.SliceStable(result, func(i, j int) bool { return result[i].Number < result[j].Number })
	for index := range result {
		if result[index].Number <= 0 {
			result[index].Number = index + 1
		}
	}
	return result
}

func catalogConfigurationID(record CatalogConfiguration) string {
	return strings.Join([]string{catalogSlug(record.Make), catalogSlug(record.Model), strconv.Itoa(record.Year), catalogSlug(record.Trim)}, "-")
}

func catalogSlug(value string) string {
	return slugVehicle(value)
}

func catalogMakeLabel(value string) string {
	value = strings.TrimSpace(value)
	key := strings.ToLower(strings.Join(strings.Fields(strings.ReplaceAll(value, "-", " ")), " "))
	switch key {
	case "gmc":
		return "GMC"
	case "mercedes benz":
		return "Mercedes-Benz"
	case "nissan datsun":
		return "Nissan-Datsun"
	case "nissan diesel truck ud":
		return "Nissan Diesel Truck - UD"
	default:
		return value
	}
}

func catalogLabel(value string) string {
	return strings.Join(strings.Fields(strings.TrimSpace(value)), " ")
}

var _ CatalogStore = (*memoryCatalogStore)(nil)

type postgresCatalogStore struct{ pool *pgxpool.Pool }

func newPostgresCatalogStore(pool *pgxpool.Pool) *postgresCatalogStore {
	return &postgresCatalogStore{pool: pool}
}

func (s *postgresCatalogStore) Years(ctx context.Context, _ Principal) ([]CatalogYear, error) {
	rows, err := s.pool.Query(ctx, `
		SELECT DISTINCT year FROM vehicle_catalog_years
		UNION
		SELECT DISTINCT model_year FROM vehicles
		ORDER BY year`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	result := []CatalogYear{}
	for rows.Next() {
		var year int
		if err := rows.Scan(&year); err != nil {
			return nil, err
		}
		result = append(result, CatalogYear{Year: year})
	}
	return result, rows.Err()
}

func (s *postgresCatalogStore) Makes(ctx context.Context, _ Principal, year int, region string) ([]CatalogMake, error) {
	rows, err := s.pool.Query(ctx, `
		SELECT DISTINCT make FROM vehicle_identity_bases
		WHERE model_year = $1 AND ($2 = '' OR region = $2) AND reviewer_state <> 'rejected'
		ORDER BY make`, year, region)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	result := []CatalogMake{}
	seen := map[string]bool{}
	for rows.Next() {
		var name string
		if err := rows.Scan(&name); err != nil {
			return nil, err
		}
		name = catalogMakeLabel(name)
		key := catalogSlug(name)
		if seen[key] {
			continue
		}
		seen[key] = true
		result = append(result, CatalogMake{ID: key, Name: name})
	}
	return result, rows.Err()
}

func (s *postgresCatalogStore) Models(ctx context.Context, _ Principal, year int, makeName, region string) ([]CatalogModel, error) {
	rows, err := s.pool.Query(ctx, `
		SELECT DISTINCT model FROM vehicle_identity_bases
		WHERE model_year = $1 AND LOWER(make) = LOWER($2) AND ($3 = '' OR region = $3) AND reviewer_state <> 'rejected'
		ORDER BY model`, year, makeName, region)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	result := []CatalogModel{}
	seen := map[string]bool{}
	for rows.Next() {
		var name string
		if err := rows.Scan(&name); err != nil {
			return nil, err
		}
		name = catalogLabel(name)
		key := catalogSlug(name)
		if seen[key] {
			continue
		}
		seen[key] = true
		result = append(result, CatalogModel{ID: key, Name: name})
	}
	return result, rows.Err()
}

func (s *postgresCatalogStore) Configurations(ctx context.Context, _ Principal, year int, makeName, model, region string) ([]CatalogConfiguration, error) {
	rows, err := s.pool.Query(ctx, `
		SELECT vc.vehicle_configuration_id::text, vc.vehicle_id::text,
		       vib.model_year, vib.make, vib.model, vib.region,
		       COALESCE(vc.trim, ''), COALESCE(vc.engine_displacement_l::text, ''),
		       vib.reviewer_state <> 'rejected' AND vc.reviewer_state <> 'rejected'
		FROM vehicle_configurations vc
		JOIN vehicle_identity_bases vib ON vib.vehicle_identity_base_id = vc.vehicle_identity_base_id
		WHERE vib.model_year = $1 AND LOWER(vib.make) = LOWER($2) AND LOWER(vib.model) = LOWER($3)
		  AND ($4 = '' OR vib.region = $4)
		  AND vib.reviewer_state <> 'rejected' AND vc.reviewer_state <> 'rejected'
		ORDER BY vc.vehicle_configuration_id`, year, makeName, model, region)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	result := []CatalogConfiguration{}
	for rows.Next() {
		var record CatalogConfiguration
		if err := rows.Scan(&record.ID, &record.VehicleID, &record.Year, &record.Make, &record.Model, &record.Region, &record.Trim, &record.Engine, &record.Complete); err != nil {
			return nil, err
		}
		result = append(result, record)
	}
	return result, rows.Err()
}

func (s *postgresCatalogStore) CatalogScopeComplete(ctx context.Context, _ Principal, scope string, year int, makeName, model, region string) (bool, error) {
	if scope != "makes" && scope != "models" && scope != "configurations" {
		return false, ErrCatalogInvalid
	}
	prefix := strconv.Itoa(year) + ":"
	if scope == "models" || scope == "configurations" {
		prefix += makeName + ":"
	}
	if scope == "configurations" {
		prefix += model + ":"
	}
	var complete bool
	err := s.pool.QueryRow(ctx, `
		SELECT EXISTS (
			SELECT 1
			FROM vehicle_catalog_hydration_scopes
			WHERE scope = $1 AND model_year = $2
			  AND ($3 = '' OR LOWER(make) = LOWER($3))
			  AND ($4 = '' OR LOWER(model) = LOWER($4))
			  AND ($5 = '' OR region = $5)
		)
		OR EXISTS (
			SELECT 1
			FROM vehicle_catalog_sync_scopes scope_row
			JOIN vehicle_catalog_syncs sync ON sync.vehicle_catalog_sync_id = scope_row.vehicle_catalog_sync_id
			WHERE sync.provider = 'autoapitwo'
			  AND sync.status = 'completed'
			  AND scope_row.status = 'completed'
			  AND scope_row.scope_key LIKE $6 || '%'
		)`, scope, year, makeName, model, region, prefix).Scan(&complete)
	return complete, err
}

func (s *postgresCatalogStore) CatalogArticleProgress(ctx context.Context, _ Principal, vehicleID string) (*CatalogArticleProgress, error) {
	var progress CatalogArticleProgress
	err := s.pool.QueryRow(ctx, `
		SELECT status, phase, processed_units, total_units, progress_percent,
		       current_article_id, current_title, progress_detail
		FROM vehicle_catalog_hydration_scopes
		WHERE scope = 'articles' AND (
		      vehicle_id = $1
		      OR vehicle_id = (
			      SELECT vc.vehicle_id::text
			      FROM vehicle_configurations vc
			      WHERE vc.vehicle_configuration_id::text = $1
			      LIMIT 1
		      )
		)
		ORDER BY updated_at DESC
		LIMIT 1`, vehicleID).
		Scan(
			&progress.Status,
			&progress.Phase,
			&progress.Processed,
			&progress.Total,
			&progress.Percent,
			&progress.CurrentArticleID,
			&progress.CurrentTitle,
			&progress.Detail,
		)
	if errors.Is(err, pgx.ErrNoRows) {
		return nil, nil
	}
	if err != nil {
		return nil, err
	}
	return &progress, nil
}

func (s *postgresCatalogStore) ConfigurationByVehicle(ctx context.Context, _ Principal, vehicleID string) (CatalogConfiguration, error) {
	var record CatalogConfiguration
	err := s.pool.QueryRow(ctx, `
		SELECT vc.vehicle_configuration_id::text, vc.vehicle_id::text,
		       vib.model_year, vib.make, vib.model, vib.region,
		       COALESCE(vc.trim, ''), COALESCE(vc.engine_displacement_l::text, ''),
		       vib.reviewer_state <> 'rejected' AND vc.reviewer_state <> 'rejected'
		FROM vehicle_configurations vc
		JOIN vehicle_identity_bases vib ON vib.vehicle_identity_base_id = vc.vehicle_identity_base_id
		WHERE (vc.vehicle_id::text = $1 OR vc.vehicle_configuration_id::text = $1)
		  AND vib.reviewer_state <> 'rejected' AND vc.reviewer_state <> 'rejected'
		ORDER BY vc.vehicle_configuration_id LIMIT 1`, vehicleID).
		Scan(&record.ID, &record.VehicleID, &record.Year, &record.Make, &record.Model, &record.Region, &record.Trim, &record.Engine, &record.Complete)
	if errors.Is(err, pgx.ErrNoRows) {
		return CatalogConfiguration{}, ErrCatalogNotFound
	}
	if err != nil {
		return CatalogConfiguration{}, err
	}
	return record, nil
}

func (s *postgresCatalogStore) Articles(ctx context.Context, _ Principal, vehicleID string) ([]CatalogArticle, error) {
	rows, err := s.pool.Query(ctx, `
	SELECT DISTINCT ON (article_id) catalog_article_id::text, article_id, COALESCE(title, ''),
	       COALESCE(content_kind, ''), COALESCE(component, ''),
	       COALESCE(content_status, 'list_only')
	FROM catalog_articles
	WHERE (
	      vehicle_id::text = $1
	      OR EXISTS (
		      SELECT 1
		      FROM vehicle_configurations vc
		      WHERE vc.vehicle_id = catalog_articles.vehicle_id
		        AND vc.vehicle_configuration_id::text = $1
	      )
	)
	  AND article_id NOT LIKE 'L:%'
	ORDER BY article_id,
	         (content_status = 'content_complete') DESC,
	         created_at DESC,
	         catalog_article_id DESC`, vehicleID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	result := []CatalogArticle{}
	for rows.Next() {
		var record CatalogArticle
		var sourceArticleID string
		if err := rows.Scan(&record.ID, &sourceArticleID, &record.Title, &record.Kind, &record.Component, &record.ContentStatus); err != nil {
			return nil, err
		}
		record.sourceArticleID = sourceArticleID
		record.VehicleID = vehicleID
		record.Complete = record.ContentStatus == "content_complete"
		result = append(result, record)
	}
	return result, rows.Err()
}

func (s *postgresCatalogStore) Article(ctx context.Context, _ Principal, vehicleID, articleID string) (CatalogArticle, error) {
	var record CatalogArticle
	var rawSteps, rawDocument, rawImages, rawOriginal []byte
	var sourceID, sourceVersion, sourceContentSHA256, sourceURI, sourceArticleID string
	err := s.pool.QueryRow(ctx, `
		SELECT ca.catalog_article_id::text, ca.article_id, COALESCE(ca.title, ''), COALESCE(ca.content_kind, ''),
		       COALESCE(ca.component, ''), COALESCE(ca.content_status, 'list_only'),
		       COALESCE(ca.body, ''), COALESCE(ca.steps, '[]'::jsonb),
		       COALESCE(ca.normalized_document, '{}'::jsonb),
		       COALESCE(ca.images, '[]'::jsonb), COALESCE(ca.source_original, '{}'::jsonb), ca.source_snapshot_id::text,
		       COALESCE(ss.source_version, ''), COALESCE(ss.content_sha256, ''), COALESCE(ss.source_uri, '')
		FROM catalog_articles ca
		JOIN source_snapshots ss ON ss.source_snapshot_id = ca.source_snapshot_id
		WHERE (
		      ca.vehicle_id::text = $1
		      OR EXISTS (
			      SELECT 1
			      FROM vehicle_configurations vc
			      WHERE vc.vehicle_id = ca.vehicle_id
			        AND vc.vehicle_configuration_id::text = $1
		      )
		)
		  AND (ca.catalog_article_id::text = $2 OR ca.article_id = $2 OR ca.article_id = (
			      SELECT alias.article_id
			      FROM catalog_articles alias
			      WHERE alias.catalog_article_id::text = $2
			      LIMIT 1
		       ))
		ORDER BY (ca.content_status = 'content_complete') DESC,
		         ca.created_at DESC LIMIT 1`, vehicleID, articleID).
		Scan(&record.ID, &sourceArticleID, &record.Title, &record.Kind, &record.Component, &record.ContentStatus, &record.Body, &rawSteps, &rawDocument, &rawImages, &rawOriginal, &sourceID, &sourceVersion, &sourceContentSHA256, &sourceURI)
	if errors.Is(err, pgx.ErrNoRows) {
		return CatalogArticle{}, ErrCatalogNotFound
	}
	if err != nil {
		return CatalogArticle{}, err
	}
	if err := json.Unmarshal(rawSteps, &record.Steps); err != nil {
		return CatalogArticle{}, err
	}
	var document CatalogDocument
	if err := json.Unmarshal(rawDocument, &document); err == nil && len(document.Blocks) > 0 {
		record.Document = &document
	}
	if err := json.Unmarshal(rawImages, &record.Images); err != nil {
		return CatalogArticle{}, err
	}
	record.VehicleID = vehicleID
	record.sourceArticleID = sourceArticleID
	record.Complete = record.ContentStatus == "content_complete"
	record.SourceOriginal = append(json.RawMessage(nil), rawOriginal...)
	record.sourceSnapshotID = sourceID
	record.sourceVersion = sourceVersion
	record.sourceContentSHA256 = sourceContentSHA256
	record.sourceURI = sourceURI
	record.sourceFormat = catalogSourceFormat(rawOriginal)
	record.sourceAvailable = len(bytes.TrimSpace(rawOriginal)) > 2
	record.Provenance = []CatalogProvenance{{ID: sourceID, Version: sourceVersion}}
	record.Steps = orderedCatalogSteps(record.Steps)
	return record, nil
}

func (s *postgresCatalogStore) ArticleSource(ctx context.Context, _ Principal, vehicleID, articleID string) (CatalogSourceContent, error) {
	var result CatalogSourceContent
	var rawOriginal []byte
	err := s.pool.QueryRow(ctx, `
		SELECT ca.source_snapshot_id::text, COALESCE(ss.source_version, ''),
		       COALESCE(ss.content_sha256, ''), COALESCE(ss.source_uri, ''),
		       COALESCE(ca.source_original, '{}'::jsonb)
		FROM catalog_articles ca
		JOIN source_snapshots ss ON ss.source_snapshot_id = ca.source_snapshot_id
		WHERE (
		      ca.vehicle_id::text = $1
		      OR EXISTS (
			      SELECT 1
			      FROM vehicle_configurations vc
			      WHERE vc.vehicle_id = ca.vehicle_id
			        AND vc.vehicle_configuration_id::text = $1
		      )
		)
		  AND (ca.catalog_article_id::text = $2 OR ca.article_id = $2 OR ca.article_id = (
			      SELECT alias.article_id
			      FROM catalog_articles alias
			      WHERE alias.catalog_article_id::text = $2
			      LIMIT 1
		       ))
		  AND jsonb_typeof(ca.source_original) = 'object'
		  AND ca.source_original <> '{}'::jsonb
		ORDER BY (ca.content_status = 'content_complete') DESC,
		         ca.created_at DESC LIMIT 1`, vehicleID, articleID).
		Scan(&result.SnapshotID, &result.Version, &result.ContentSHA256, &result.SourceURI, &rawOriginal)
	if errors.Is(err, pgx.ErrNoRows) {
		return CatalogSourceContent{}, ErrCatalogNotFound
	}
	if err != nil {
		return CatalogSourceContent{}, err
	}
	result.Original = cloneCatalogRaw(rawOriginal)
	return result, nil
}

var _ CatalogStore = (*postgresCatalogStore)(nil)

// Keep the raw source bytes detached from callers that retain a returned record.
func cloneCatalogRaw(raw json.RawMessage) json.RawMessage { return bytes.Clone(raw) }
