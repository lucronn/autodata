package main

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"math"
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
	Years(context.Context, Principal) ([]CatalogYear, *bool, error)
	Makes(context.Context, Principal, int, string) ([]CatalogMake, error)
	Models(context.Context, Principal, int, string, string) ([]CatalogModel, error)
	Configurations(context.Context, Principal, int, string, string, string) ([]CatalogConfiguration, error)
	CatalogScopeComplete(context.Context, Principal, string, int, string, string, string) (bool, error)
	CatalogArticleProgress(context.Context, Principal, string) (*CatalogArticleProgress, error)
	ConfigurationByVehicle(context.Context, Principal, string) (CatalogConfiguration, error)
	Articles(context.Context, Principal, string) ([]CatalogArticle, error)
	Article(context.Context, Principal, string, string) (CatalogArticle, error)
	ArticleView(context.Context, Principal, string, string) (CatalogArticleView, error)
	ArticleSourceRevision(context.Context, Principal, string, string, string) (CatalogSourceContent, error)
	ArticleSource(context.Context, Principal, string, string) (CatalogSourceContent, error)
}

type CatalogYear struct {
	Year int `json:"year"`
}

type CatalogMake struct {
	ID               string `json:"id"`
	Name             string `json:"name"`
	MarketUnverified bool   `json:"market_unverified,omitempty"`
}

type CatalogModel struct {
	ID               string `json:"id"`
	Name             string `json:"name"`
	MarketUnverified bool   `json:"market_unverified,omitempty"`
}

type CatalogConfiguration struct {
	ID                            string `json:"id"`
	VehicleID                     string `json:"vehicle_id"`
	Year                          int    `json:"year"`
	Make                          string `json:"make"`
	Model                         string `json:"model"`
	Region                        string `json:"region,omitempty"`
	Trim                          string `json:"trim,omitempty"`
	Engine                        string `json:"engine,omitempty"`
	EngineVariant                 string `json:"engine_variant,omitempty"`
	EngineVariantMarketUnverified bool   `json:"engine_variant_market_unverified,omitempty"`
	ConfigurationUnresolved       bool   `json:"configuration_unresolved,omitempty"`
	BodyStyle                     string `json:"body_style,omitempty"`
	Drivetrain                    string `json:"drivetrain,omitempty"`
	Complete                      bool   `json:"complete"`
}

type CatalogProvenance struct {
	ID      string `json:"id"`
	Version string `json:"version,omitempty"`
}

type CatalogStep struct {
	Action       string          `json:"action,omitempty"`
	Images       *[]CatalogImage `json:"images,omitempty"`
	Text         string          `json:"text,omitempty"`
	EvidenceIDs  []string        `json:"evidence_ids,omitempty"`
	Number       int             `json:"number,omitempty"`
	Heading      string          `json:"heading,omitempty"`
	Instructions []string        `json:"instructions"`
	ImageIDs     []string        `json:"image_ids,omitempty"`
	explicitZero bool
}

// R2 source steps retain text; canonical steps retain action and following
// instructions separately. Missing canonical numbers stay absent, and an
// optional image slice distinguishes absent images from an explicit empty list.
func (step *CatalogStep) UnmarshalJSON(data []byte) error {
	type plain CatalogStep
	var value struct {
		plain
		Number *int `json:"number"`
	}
	if err := json.Unmarshal(data, &value); err != nil {
		return err
	}
	*step = CatalogStep(value.plain)
	if value.Number != nil {
		step.Number = *value.Number
		step.explicitZero = step.Number == 0
	}
	if step.Action == "" && len(step.Instructions) == 0 && step.Text != "" {
		step.Instructions = []string{step.Text}
	}
	return nil
}

func (step CatalogStep) MarshalJSON() ([]byte, error) {
	type plain CatalogStep
	if step.Number != 0 || !step.explicitZero {
		return json.Marshal(plain(step))
	}
	return json.Marshal(struct {
		plain
		Number int `json:"number"`
	}{plain: plain(step), Number: step.Number})
}

type CatalogDocument struct {
	SchemaVersion        int                    `json:"schema_version"`
	NormalizationVersion string                 `json:"normalization_version"`
	Blocks               []CatalogDocumentBlock `json:"blocks"`
}

type CatalogDocumentBlock struct {
	Images            []CatalogImage       `json:"images,omitempty"`
	Caption           string               `json:"caption,omitempty"`
	BlockID           string               `json:"block_id,omitempty"`
	SourceOrder       int                  `json:"source_order,omitempty"`
	Type              string               `json:"type"`
	Level             int                  `json:"level,omitempty"`
	Number            int                  `json:"number,omitempty"`
	Start             *int32               `json:"start,omitempty"`
	Text              string               `json:"text,omitempty"`
	Label             string               `json:"label,omitempty"`
	Href              string               `json:"href,omitempty"`
	TargetArticleID   string               `json:"target_article_id,omitempty"`
	Columns           []any                `json:"columns,omitempty"`
	Rows              [][]any              `json:"rows,omitempty"`
	Items             []any                `json:"items,omitempty"`
	AssetID           string               `json:"asset_id,omitempty"`
	ImageID           string               `json:"image_id,omitempty"`
	Alt               string               `json:"alt,omitempty"`
	Status            string               `json:"status,omitempty"`
	UnavailableReason string               `json:"unavailable_reason,omitempty"`
	EvidenceIDs       []string             `json:"evidence_ids,omitempty"`
	SourceLocator     string               `json:"source_locator,omitempty"`
	FigureLayout      *CatalogFigureLayout `json:"figure_layout,omitempty"`
}

// Table rows in stored documents may be arrays or objects containing cells.
// Keep the established array projection for top-level rows.
func (block *CatalogDocumentBlock) UnmarshalJSON(data []byte) error {
	type plain CatalogDocumentBlock
	var decoded struct {
		plain
		Rows            []json.RawMessage `json:"rows"`
		Start           any               `json:"start"`
		TargetArticleID any               `json:"target_article_id"`
		FigureLayout    any               `json:"figure_layout"`
	}
	if err := json.Unmarshal(data, &decoded); err != nil {
		return err
	}
	if number, ok := catalogJSONListNumber(decoded.Start); ok && decoded.plain.Type == "ordered_list" {
		decoded.plain.Start = &number
	}
	if decoded.plain.Type == "image" {
		decoded.plain.FigureLayout = parseCatalogFigureLayout(decoded.FigureLayout)
	}
	if target, ok := decoded.TargetArticleID.(string); ok && decoded.plain.Type == "link" && commerceUUID(target) {
		decoded.plain.TargetArticleID = target
	}
	if decoded.Rows != nil {
		decoded.plain.Rows = make([][]any, 0, len(decoded.Rows))
	}
	for _, raw := range decoded.Rows {
		var cells []any
		if bytes.HasPrefix(bytes.TrimSpace(raw), []byte("{")) {
			var row struct {
				Cells []any `json:"cells"`
			}
			if err := json.Unmarshal(raw, &row); err != nil {
				return err
			}
			cells = row.Cells
		} else if err := json.Unmarshal(raw, &cells); err != nil {
			return err
		}
		decoded.plain.Rows = append(decoded.plain.Rows, cells)
	}
	*block = CatalogDocumentBlock(decoded.plain)
	return nil
}

// Numbers in untyped JSON list items and nested blocks decode as float64.
func catalogJSONListNumber(value any) (int32, bool) {
	number, ok := value.(float64)
	if !ok || number < math.MinInt32 || number > math.MaxInt32 {
		return 0, false
	}
	integer := int32(number)
	return integer, float64(integer) == number
}

func catalogJSONTableSpan(attribute string, value any) (int32, bool) {
	number, ok := catalogJSONListNumber(value)
	limit := int32(1000)
	if attribute == "rowspan" {
		limit = 65534
	}
	return number, ok && number > 1 && number <= limit
}

func catalogNestedBlocks(value any) []CatalogDocumentBlock {
	if value == nil {
		return nil
	}
	raw, err := json.Marshal(value)
	if err != nil {
		return nil
	}
	var blocks []CatalogDocumentBlock
	if err := json.Unmarshal(raw, &blocks); err != nil {
		return nil
	}
	return blocks
}

type CatalogArticle struct {
	CanonicalArticleID       *string              `json:"canonical_article_id"`
	SourceRevisionID         *string              `json:"source_revision_id"`
	CanonicalRevisionID      *string              `json:"canonical_revision_id"`
	ContentOrigin            *string              `json:"content_origin"`
	SourceBodyPreview        bool                 `json:"source_body_preview,omitempty"`
	Availability             string               `json:"availability"`
	ViewRevision             *string              `json:"view_revision"`
	ReviewStatus             *string              `json:"review_status"`
	Processing               *CatalogProcessing   `json:"processing"`
	ID                       string               `json:"id"`
	VehicleID                string               `json:"vehicle_id"`
	Title                    string               `json:"title"`
	Kind                     string               `json:"kind,omitempty"`
	Component                string               `json:"component,omitempty"`
	ServiceSchedule          string               `json:"service_schedule,omitempty"`
	ContentStatus            string               `json:"content_status"`
	Complete                 bool                 `json:"complete"`
	Body                     string               `json:"body,omitempty"`
	Steps                    []CatalogStep        `json:"steps,omitempty"`
	Document                 *CatalogDocument     `json:"document,omitempty"`
	Images                   []CatalogImage       `json:"images"`
	Provenance               []CatalogProvenance  `json:"provenance,omitempty"`
	SourceReview             *CatalogSourceReview `json:"source_review,omitempty"`
	OriginalSourceReview     *CatalogSourceReview `json:"original_source_review,omitempty"`
	SourceOriginal           json.RawMessage      `json:"-"`
	canonicalVehicleID       string
	canonicalConfigurationID *string
	sourceArticleID          string
	sourceSnapshotID         string
	sourceVersion            string
	sourceContentSHA256      string
	sourceURI                string
	sourceFormat             string
	sourceAvailable          bool
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
	Document         *CatalogDocument
	Images           []CatalogImage
	ViewRevision     *string
	SourceRevisionID *string
	SnapshotID       string
	Version          string
	ContentSHA256    string
	SourceURI        string
	Original         json.RawMessage
}

type CatalogArticleProgress struct {
	Complete         bool   `json:"complete"`
	CatalogEmpty     bool   `json:"catalog_empty,omitempty"`
	Retryable        bool   `json:"retryable"`
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
	AssetID           string               `json:"asset_id,omitempty"`
	Caption           string               `json:"caption,omitempty"`
	ID                string               `json:"id,omitempty"`
	URL               string               `json:"url,omitempty"`
	Alt               string               `json:"alt,omitempty"`
	StorageKey        string               `json:"-"`
	MediaType         string               `json:"media_type,omitempty"`
	ImageID           string               `json:"image_id,omitempty"`
	Status            string               `json:"status,omitempty"`
	UnavailableReason string               `json:"unavailable_reason,omitempty"`
	FigureLayout      *CatalogFigureLayout `json:"figure_layout,omitempty"`
}

// UnmarshalJSON retains the private storage locator from persisted article
// JSON. StorageKey remains excluded from public JSON by its struct tag.
func (image *CatalogImage) UnmarshalJSON(data []byte) error {
	type publicImage CatalogImage
	var decoded struct {
		publicImage
		StorageKey   string `json:"storage_key"`
		FigureLayout any    `json:"figure_layout"`
	}
	if err := json.Unmarshal(data, &decoded); err != nil {
		return err
	}
	decoded.publicImage.FigureLayout = parseCatalogFigureLayout(decoded.FigureLayout)
	*image = CatalogImage(decoded.publicImage)
	image.StorageKey = decoded.StorageKey
	image.ImageID = publicCatalogAssetID(image.ImageID)
	image.AssetID = publicCatalogAssetID(image.AssetID)
	if image.ImageID != "" {
		image.AssetID = image.ImageID
		if image.ID == "" {
			image.ID = image.ImageID
		}
	}
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

func (s *memoryCatalogStore) Years(context.Context, Principal) ([]CatalogYear, *bool, error) {
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
	return result, nil, nil
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
		if record.Year == year && catalogSelectorMatches(record.Make, makeName) && (region == "" || strings.EqualFold(record.Region, region)) {
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
		if record.Year == year && catalogSelectorMatches(record.Make, makeName) && catalogSelectorMatches(record.Model, model) && (region == "" || strings.EqualFold(record.Region, region)) {
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
		if scope != "makes" && !catalogSelectorMatches(record.Make, makeName) {
			continue
		}
		if scope == "configurations" && !catalogSelectorMatches(record.Model, model) {
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

// Public selector IDs discard punctuation as well as letter case. Match the same
// normalized value used to emit IDs, while preserving literal-label lookup.
func catalogSelectorMatches(label, selector string) bool {
	return strings.EqualFold(label, selector) || (catalogSlug(selector) != "" && catalogSlug(label) == catalogSlug(selector))
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

func (s *postgresCatalogStore) Years(ctx context.Context, _ Principal) ([]CatalogYear, *bool, error) {
	var years []int32
	var complete *bool
	// An older worker can finish the manifest while newer progress exists.
	// Individual inventory rows do not prove the year enumeration is complete.
	err := s.pool.QueryRow(ctx, `
		WITH manifest AS (
			SELECT year FROM vehicle_catalog_years
		), durable AS (
			SELECT checkpoint->'provider_years' AS provider_years, status = 'completed' AS complete
			FROM vehicle_catalog_syncs
			WHERE provider = 'workshop' AND source_version = 'global-years'
			  AND traversal_version = 'initial-selector-v1' AND status IN ('partial', 'completed')
		)
		SELECT ARRAY(
			SELECT year FROM manifest
			UNION
			SELECT model_year FROM vehicles
			UNION
			SELECT remembered.year
			FROM durable, jsonb_each(durable.provider_years) AS supplier,
				jsonb_to_recordset(supplier.value->'records') AS remembered(year integer)
			WHERE NOT EXISTS (SELECT 1 FROM manifest) AND remembered.year BETWEEN 1886 AND 2100
			ORDER BY year
		), CASE WHEN EXISTS (SELECT 1 FROM manifest) THEN true ELSE (SELECT complete FROM durable) END`).
		Scan(&years, &complete)
	if err != nil {
		return nil, nil, err
	}
	result := make([]CatalogYear, 0, len(years))
	for _, year := range years {
		result = append(result, CatalogYear{Year: int(year)})
	}
	return result, complete, nil
}

func (s *postgresCatalogStore) Makes(ctx context.Context, _ Principal, year int, region string) ([]CatalogMake, error) {
	rows, err := s.pool.Query(ctx, `
		SELECT DISTINCT make, reviewer_state = 'approved' AS market_known FROM vehicle_identity_bases
		WHERE model_year = $1 AND ($2 = '' OR region = $2) AND reviewer_state <> 'rejected'
		UNION
		SELECT item->>'make' AS make, COALESCE(item->>'source_region', '') = hydration.region
		FROM vehicle_catalog_hydration_scopes hydration,
		     jsonb_array_elements(hydration.selector_rows) AS item
		WHERE hydration.scope = 'makes' AND hydration.model_year = $1
		  AND ($2 = '' OR hydration.region = $2)
		  AND COALESCE(item->>'source_region', '') IN ('', hydration.region)
		  AND COALESCE(item->>'make', '') <> ''
		ORDER BY make, market_known DESC`, year, region)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	result := []CatalogMake{}
	seen := map[string]int{}
	for rows.Next() {
		var name string
		var marketKnown bool
		if err := rows.Scan(&name, &marketKnown); err != nil {
			return nil, err
		}
		name = catalogMakeLabel(name)
		key := catalogSlug(name)
		if index, duplicate := seen[key]; duplicate {
			result[index].MarketUnverified = result[index].MarketUnverified && !marketKnown
			continue
		}
		seen[key] = len(result)
		result = append(result, CatalogMake{ID: key, Name: name, MarketUnverified: region != "" && !marketKnown})
	}
	return result, rows.Err()
}

func (s *postgresCatalogStore) Models(ctx context.Context, _ Principal, year int, makeName, region string) ([]CatalogModel, error) {
	rows, err := s.pool.Query(ctx, `
		SELECT DISTINCT model, reviewer_state = 'approved' AS market_known FROM vehicle_identity_bases
		WHERE model_year = $1 AND (LOWER(make) = LOWER($2) OR ($4 <> '' AND TRIM(BOTH '-' FROM REGEXP_REPLACE(LOWER(make), '[^a-z0-9]+', '-', 'g')) = $4)) AND ($3 = '' OR region = $3) AND reviewer_state <> 'rejected'
		  AND model NOT LIKE '\_%'
		UNION
		SELECT item->>'model' AS model, COALESCE(item->>'source_region', '') = hydration.region
		FROM vehicle_catalog_hydration_scopes hydration,
		     jsonb_array_elements(hydration.selector_rows) AS item
		WHERE hydration.scope = 'models' AND hydration.model_year = $1
		  AND (LOWER(hydration.make) = LOWER($2) OR ($4 <> '' AND TRIM(BOTH '-' FROM REGEXP_REPLACE(LOWER(hydration.make), '[^a-z0-9]+', '-', 'g')) = $4)) AND ($3 = '' OR hydration.region = $3)
		  AND COALESCE(item->>'source_region', '') IN ('', hydration.region)
		  AND COALESCE(item->>'model', '') <> '' AND item->>'model' NOT LIKE '\_%'
		ORDER BY model, market_known DESC`, year, makeName, region, catalogSlug(makeName))
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	result := []CatalogModel{}
	seen := map[string]int{}
	for rows.Next() {
		var name string
		var marketKnown bool
		if err := rows.Scan(&name, &marketKnown); err != nil {
			return nil, err
		}
		name = catalogLabel(name)
		key := catalogSlug(name)
		if index, duplicate := seen[key]; duplicate {
			result[index].MarketUnverified = result[index].MarketUnverified && !marketKnown
			continue
		}
		seen[key] = len(result)
		result = append(result, CatalogModel{ID: key, Name: name, MarketUnverified: region != "" && !marketKnown})
	}
	return result, rows.Err()
}

// Order each limited evidence probe by its existing index so rechecking a
// source-less selector does not scan the whole article catalog.
const catalogConfigurationFields = `vc.vehicle_configuration_id::text, vc.vehicle_id::text,
		       vib.model_year, vib.make, vib.model, vib.region,
		       COALESCE(vc.trim, ''), COALESCE(vc.engine_displacement_l::text, ''), COALESCE(vc.engine_variant, ''),
		       vc.engine_variant IS NOT NULL AND NOT vc.engine_variant_market_verified,
		       COALESCE(btrim(vib.body_style), ''), COALESCE(btrim(vib.drivetrain), ''),
		       vib.reviewer_state <> 'rejected' AND vc.reviewer_state <> 'rejected',
		       CASE
		         WHEN COALESCE(vc.trim, '') ~ '[^[:space:]]' OR vc.engine_displacement_l IS NOT NULL
		           OR COALESCE(vc.engine_variant, '') ~ '[^[:space:]]'
		           OR COALESCE(vib.drivetrain, '') ~ '[^[:space:]]' THEN false
		         ELSE NOT (
		           EXISTS (
		             SELECT 1 FROM vehicle_provider_mappings mapping
		             WHERE mapping.vehicle_id = vc.vehicle_id
		               AND mapping.vehicle_configuration_id = vc.vehicle_configuration_id
		               AND mapping.provider IN ('bankone','banktwo')
		               AND mapping.entity_type = 'car' AND mapping.mapping_status = 'verified'
		             GROUP BY mapping.provider
		             HAVING count(DISTINCT mapping.provider_id) = 1
		               AND bool_and(mapping.provider_id ~ '[^[:space:]]')
		           )
		           OR COALESCE((
		             SELECT true FROM catalog_article_provider_scopes scope
		             WHERE scope.scope_key = 'configuration:' || vc.vehicle_configuration_id::text
		               AND scope.provider_slug IN ('bankone','banktwo')
		               AND scope.source_vehicle_ref ~ '[^[:space:]]'
		             ORDER BY scope.scope_key, scope.provider_slug
		             LIMIT 1
		           ), false)
		           OR COALESCE((
		             SELECT true FROM canonical_articles article
		             WHERE article.scope_key = 'configuration:' || vc.vehicle_configuration_id::text
		               AND article.provider_slug IN ('bankone','banktwo')
		               AND article.membership_status = 'active' AND article.takedown_status = 'active'
		             ORDER BY article.provider_slug, article.scope_key, article.source_vehicle_ref, article.source_article_ref
		             LIMIT 1
		           ), false)
		         )
		       END`

func (s *postgresCatalogStore) Configurations(ctx context.Context, _ Principal, year int, makeName, model, region string) ([]CatalogConfiguration, error) {
	rows, err := s.pool.Query(ctx, `
		SELECT `+catalogConfigurationFields+`
		FROM vehicle_configurations vc
		JOIN vehicle_identity_bases vib ON vib.vehicle_identity_base_id = vc.vehicle_identity_base_id
		WHERE vib.model_year = $1 AND (LOWER(vib.make) = LOWER($2) OR ($5 <> '' AND TRIM(BOTH '-' FROM REGEXP_REPLACE(LOWER(vib.make), '[^a-z0-9]+', '-', 'g')) = $5))
		  AND (LOWER(vib.model) = LOWER($3) OR ($6 <> '' AND TRIM(BOTH '-' FROM REGEXP_REPLACE(LOWER(vib.model), '[^a-z0-9]+', '-', 'g')) = $6))
		  AND ($4 = '' OR vib.region = $4)
		  AND vib.reviewer_state <> 'rejected' AND vc.reviewer_state <> 'rejected'
		ORDER BY vc.vehicle_configuration_id`, year, makeName, model, region, catalogSlug(makeName), catalogSlug(model))
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	result := []CatalogConfiguration{}
	for rows.Next() {
		var record CatalogConfiguration
		if err := rows.Scan(
			&record.ID, &record.VehicleID, &record.Year, &record.Make, &record.Model, &record.Region,
			&record.Trim, &record.Engine, &record.EngineVariant, &record.EngineVariantMarketUnverified, &record.BodyStyle, &record.Drivetrain, &record.Complete,
			&record.ConfigurationUnresolved,
		); err != nil {
			return nil, err
		}
		result = append(result, record)
	}
	return result, rows.Err()
}

func (s *postgresCatalogStore) CatalogScopeComplete(ctx context.Context, _ Principal, scope string, year int, makeName, model, region string) (bool, error) {
	complete, _, err := s.catalogScopeCoverage(ctx, scope, year, makeName, model, region)
	return complete, err
}

func (s *postgresCatalogStore) configurationCoverage(ctx context.Context, year int, makeName, model, region string) (bool, bool, error) {
	return s.catalogScopeCoverage(ctx, "configurations", year, makeName, model, region)
}

func (s *postgresCatalogStore) catalogScopeCoverage(ctx context.Context, scope string, year int, makeName, model, region string) (bool, bool, error) {
	if scope != "makes" && scope != "models" && scope != "configurations" {
		return false, false, ErrCatalogInvalid
	}
	prefix := strconv.Itoa(year) + ":"
	if scope == "models" || scope == "configurations" {
		prefix += makeName + ":"
	}
	if scope == "configurations" {
		prefix += model + ":"
	}
	var complete, providerComplete bool
	err := s.pool.QueryRow(ctx, `
		SELECT COALESCE(bool_or($1 = 'configurations' OR completion_version = 1), false) OR EXISTS (
			SELECT 1
			FROM vehicle_catalog_sync_scopes scope_row
			JOIN vehicle_catalog_syncs sync ON sync.vehicle_catalog_sync_id = scope_row.vehicle_catalog_sync_id
			WHERE $1 = 'configurations' AND sync.provider = 'autoapitwo'
			  AND sync.status = 'completed'
			  AND scope_row.status = 'completed'
			  AND scope_row.scope_key LIKE $6 || '%'
		), COALESCE(bool_or(completion_version = 1), false)
		FROM vehicle_catalog_hydration_scopes
		WHERE scope = $1 AND model_year = $2
		  AND ($3 = '' OR LOWER(make) = LOWER($3) OR ($7 <> '' AND TRIM(BOTH '-' FROM REGEXP_REPLACE(LOWER(make), '[^a-z0-9]+', '-', 'g')) = $7))
		  AND ($4 = '' OR LOWER(model) = LOWER($4) OR ($8 <> '' AND TRIM(BOTH '-' FROM REGEXP_REPLACE(LOWER(model), '[^a-z0-9]+', '-', 'g')) = $8))
		  AND ($5 = '' OR region = $5)`, scope, year, makeName, model, region, prefix, catalogSlug(makeName), catalogSlug(model)).Scan(&complete, &providerComplete)
	return complete, providerComplete, err
}

func (s *postgresCatalogStore) CatalogArticleProgress(ctx context.Context, _ Principal, vehicleID string) (*CatalogArticleProgress, error) {
	// The scope check constraint binds each key to the corresponding vehicle or exact configuration.
	var total, completed, active, failed, retryable int
	var catalogEmpty bool
	err := s.pool.QueryRow(ctx, `
  SELECT count(*),
    count(*) FILTER(WHERE scope.status='complete' AND scope.completed_generation=scope.generation),
    count(*) FILTER(WHERE job.status IN ('pending','processing')),
    count(*) FILTER(WHERE scope.status IN ('partial','failed','needs_review','not_configured')
      OR job.status IN ('failed','needs_review','dead_letter')),
    count(*) FILTER(WHERE job.status='failed' AND job.retryable=true
      AND job.retry_count < job.max_attempts),
    CASE WHEN count(*) FILTER(WHERE scope.scope_key='configuration:'||$1
      AND scope.status='complete' AND scope.completed_generation=scope.generation AND scope.row_count=0)=2
    THEN NOT EXISTS (
      SELECT 1 FROM canonical_articles a WHERE a.scope_key='configuration:'||$1
        AND a.provider_slug IN ('bankone','banktwo') AND a.membership_status='active'
    ) ELSE false END
  FROM catalog_article_provider_scopes scope
  LEFT JOIN source_fetch_jobs job ON job.source_fetch_job_id=scope.current_job_id
  WHERE scope.scope_key IN ('vehicle:'||$1, 'configuration:'||$1)
    AND scope.provider_slug IN ('bankone','banktwo')`, vehicleID).Scan(&total, &completed, &active, &failed, &retryable, &catalogEmpty)
	if err != nil {
		return nil, err
	}
	progress := &CatalogArticleProgress{Status: "pending", Phase: "indexing", Total: 2, Processed: completed, Percent: completed * 50, Complete: total == 2 && completed == 2, Retryable: retryable > 0}
	progress.CatalogEmpty = progress.Complete && catalogEmpty
	if progress.Complete {
		progress.Status = "completed"
	} else if active > 0 {
		progress.Status = "running"
	} else if failed > 0 {
		progress.Status = "failed"
	}
	return progress, nil
}

func (s *postgresCatalogStore) ConfigurationByVehicle(ctx context.Context, _ Principal, vehicleID string) (CatalogConfiguration, error) {
	if !commerceUUID(vehicleID) {
		return CatalogConfiguration{}, ErrCatalogNotFound
	}
	var record CatalogConfiguration
	err := s.pool.QueryRow(ctx, `
		SELECT `+catalogConfigurationFields+`
		FROM vehicle_configurations vc
		JOIN vehicle_identity_bases vib ON vib.vehicle_identity_base_id = vc.vehicle_identity_base_id
		WHERE (vc.vehicle_id = $1::uuid OR vc.vehicle_configuration_id = $1::uuid)
		  AND vib.reviewer_state <> 'rejected' AND vc.reviewer_state <> 'rejected'
		ORDER BY vc.vehicle_configuration_id <> $1::uuid, vc.engine_variant IS NOT NULL, vc.vehicle_configuration_id LIMIT 1`, vehicleID).
		Scan(
			&record.ID, &record.VehicleID, &record.Year, &record.Make, &record.Model, &record.Region,
			&record.Trim, &record.Engine, &record.EngineVariant, &record.EngineVariantMarketUnverified, &record.BodyStyle, &record.Drivetrain, &record.Complete,
			&record.ConfigurationUnresolved,
		)
	if errors.Is(err, pgx.ErrNoRows) {
		return CatalogConfiguration{}, ErrCatalogNotFound
	}
	if err != nil {
		return CatalogConfiguration{}, err
	}
	return record, nil
}

func (s *postgresCatalogStore) legacyArticle(ctx context.Context, _ Principal, vehicleID, articleID string) (CatalogArticle, error) {
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
		WHERE (ca.vehicle_id::text=$1 AND ca.vehicle_configuration_id IS NULL OR ca.vehicle_configuration_id::text=$1 AND EXISTS(SELECT 1 FROM vehicle_configurations vc JOIN vehicle_identity_bases vb USING(vehicle_identity_base_id) WHERE vc.vehicle_configuration_id=ca.vehicle_configuration_id AND vc.reviewer_state<>'rejected' AND vb.reviewer_state<>'rejected'))
		  AND ca.catalog_article_id = $2::uuid AND NOT EXISTS (SELECT 1 FROM canonical_article_aliases x JOIN canonical_articles owner ON owner.canonical_article_id=x.canonical_article_id WHERE x.catalog_article_id=ca.catalog_article_id AND owner.vehicle_id=ca.vehicle_id AND owner.vehicle_configuration_id IS NOT DISTINCT FROM ca.vehicle_configuration_id) AND ss.takedown_status='active' AND NOT EXISTS (SELECT 1 FROM source_review_items review WHERE review.item_kind='quarantine' AND review.status<>'approved' AND review.source_snapshot_ids ? ca.source_snapshot_id::text)
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

func (s *postgresCatalogStore) legacyArticleSource(ctx context.Context, _ Principal, vehicleID, articleID string) (CatalogSourceContent, error) {
	var result CatalogSourceContent
	var rawOriginal []byte
	err := s.pool.QueryRow(ctx, `
		SELECT ca.source_snapshot_id::text, COALESCE(ss.source_version, ''),
		       COALESCE(ss.content_sha256, ''), COALESCE(ss.source_uri, ''),
		       COALESCE(ca.source_original, '{}'::jsonb)
		FROM catalog_articles ca
		JOIN source_snapshots ss ON ss.source_snapshot_id = ca.source_snapshot_id
		WHERE (ca.vehicle_id::text=$1 AND ca.vehicle_configuration_id IS NULL OR ca.vehicle_configuration_id::text=$1 AND EXISTS(SELECT 1 FROM vehicle_configurations vc JOIN vehicle_identity_bases vb USING(vehicle_identity_base_id) WHERE vc.vehicle_configuration_id=ca.vehicle_configuration_id AND vc.reviewer_state<>'rejected' AND vb.reviewer_state<>'rejected'))
		  AND ca.catalog_article_id = $2::uuid AND NOT EXISTS (SELECT 1 FROM canonical_article_aliases x JOIN canonical_articles owner ON owner.canonical_article_id=x.canonical_article_id WHERE x.catalog_article_id=ca.catalog_article_id AND owner.vehicle_id=ca.vehicle_id AND owner.vehicle_configuration_id IS NOT DISTINCT FROM ca.vehicle_configuration_id) AND ss.takedown_status='active' AND NOT EXISTS (SELECT 1 FROM source_review_items review WHERE review.item_kind='quarantine' AND review.status<>'approved' AND review.source_snapshot_ids ? ca.source_snapshot_id::text)
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
