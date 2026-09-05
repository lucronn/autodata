package main

import (
	"errors"
	"sort"
	"strconv"
	"strings"
	"sync"
	"time"
)

var (
	ErrVehicleIdentityInvalid  = errors.New("vehicle identity input is invalid")
	ErrVehicleIdentityConflict = errors.New("vehicle identity request conflicts with an existing request")
)

type VehicleIdentityRow struct {
	Year                any      `json:"year"`
	Make                string   `json:"make"`
	Model               string   `json:"model"`
	Region              string   `json:"region,omitempty"`
	BodyStyle           string   `json:"body_style,omitempty"`
	Trim                string   `json:"trim,omitempty"`
	Drivetrain          string   `json:"drivetrain,omitempty"`
	EngineDisplacementL *float64 `json:"engine_displacement_l,omitempty"`
}

type VehicleIdentityResolveInput struct {
	Vehicles []VehicleIdentityRow `json:"vehicles"`
}

type VehicleConfigurationRecord struct {
	ConfigurationKey    string   `json:"configuration_key"`
	Trim                string   `json:"trim,omitempty"`
	EngineDisplacementL *float64 `json:"engine_displacement_l,omitempty"`
	Drivetrain          string   `json:"drivetrain,omitempty"`
}

type VehicleIdentityRecord struct {
	Status         string                       `json:"status"`
	VehicleIDKey   string                       `json:"vehicle_id_key"`
	Year           int                          `json:"year"`
	Make           string                       `json:"make"`
	Model          string                       `json:"model"`
	Region         string                       `json:"region,omitempty"`
	BodyStyle      string                       `json:"body_style,omitempty"`
	Drivetrain     string                       `json:"drivetrain,omitempty"`
	Configurations []VehicleConfigurationRecord `json:"configurations"`
	Conflicts      []map[string]string          `json:"conflicts,omitempty"`
}

type VehicleIdentityResolveRecord struct {
	Status    string                  `json:"status"`
	Vehicles  []VehicleIdentityRecord `json:"vehicles"`
	UpdatedAt string                  `json:"updated_at"`
}

type VehicleIdentitySelectors struct {
	Makes                []string                `json:"makes"`
	Models               []string                `json:"models"`
	Years                []int                   `json:"years"`
	Drivetrains          []string                `json:"drivetrains"`
	Trims                []string                `json:"trims"`
	EngineDisplacementsL []float64               `json:"engine_displacements_l"`
	Vehicles             []VehicleIdentityRecord `json:"vehicles"`
}

type VehicleIdentityStore interface {
	Resolve(Principal, VehicleIdentityResolveInput, string) (VehicleIdentityResolveRecord, bool, error)
	Selectors(Principal) (VehicleIdentitySelectors, error)
}

type memoryVehicleIdentityStore struct {
	mu            sync.Mutex
	byIdempotency map[string]vehicleIdentityCachedRequest
	rows          []VehicleIdentityRow
}

type vehicleIdentityCachedRequest struct {
	organizationID string
	record         VehicleIdentityResolveRecord
}

func newMemoryVehicleIdentityStore() *memoryVehicleIdentityStore {
	return &memoryVehicleIdentityStore{byIdempotency: make(map[string]vehicleIdentityCachedRequest)}
}

func (s *memoryVehicleIdentityStore) Resolve(principal Principal, input VehicleIdentityResolveInput, idempotencyKey string) (VehicleIdentityResolveRecord, bool, error) {
	s.mu.Lock()
	defer s.mu.Unlock()
	if existing, ok := s.byIdempotency[idempotencyKey]; ok {
		if existing.organizationID != principal.OrganizationID {
			return VehicleIdentityResolveRecord{}, false, ErrVehicleIdentityConflict
		}
		return existing.record, true, nil
	}
	if len(input.Vehicles) == 0 {
		return VehicleIdentityResolveRecord{}, false, ErrVehicleIdentityInvalid
	}
	records, canonicalRows, err := normalizeVehicleIdentityRows(input.Vehicles)
	if err != nil {
		return VehicleIdentityResolveRecord{}, false, err
	}
	status := "resolved"
	for _, vehicle := range records {
		if vehicle.Status == "needs_review" {
			status = "needs_review"
			break
		}
	}
	record := VehicleIdentityResolveRecord{Status: status, Vehicles: records, UpdatedAt: time.Now().UTC().Format(time.RFC3339)}
	s.byIdempotency[idempotencyKey] = vehicleIdentityCachedRequest{organizationID: principal.OrganizationID, record: record}
	s.rows = append(s.rows, canonicalRows...)
	return record, false, nil
}

func (s *memoryVehicleIdentityStore) Selectors(_ Principal) (VehicleIdentitySelectors, error) {
	s.mu.Lock()
	defer s.mu.Unlock()
	makes, models, drivetrains, trims := map[string]bool{}, map[string]bool{}, map[string]bool{}, map[string]bool{}
	engines := map[float64]bool{}
	years := map[int]bool{}
	for _, row := range s.rows {
		if row.Make != "" {
			makes[row.Make] = true
		}
		if row.Model != "" {
			models[row.Model] = true
		}
		if row.Drivetrain != "" {
			drivetrains[row.Drivetrain] = true
		}
		if row.Drivetrain == "" {
			delete(drivetrains, "")
		}
		if strings.TrimSpace(row.Trim) != "" {
			trims[strings.TrimSpace(row.Trim)] = true
		}
		if row.EngineDisplacementL != nil {
			engines[*row.EngineDisplacementL] = true
		}
		years[normalizedVehicleYear(row.Year)] = true
	}
	records, _, err := normalizeVehicleIdentityRows(s.rows)
	if err != nil {
		return VehicleIdentitySelectors{}, err
	}
	return VehicleIdentitySelectors{
		Makes:                sortedStrings(makes),
		Models:               sortedStrings(models),
		Years:                sortedInts(years),
		Drivetrains:          sortedStrings(drivetrains),
		Trims:                sortedStrings(trims),
		EngineDisplacementsL: sortedFloats(engines),
		Vehicles:             records,
	}, nil
}

func normalizeVehicleIdentityRows(rows []VehicleIdentityRow) ([]VehicleIdentityRecord, []VehicleIdentityRow, error) {
	type family struct {
		record  VehicleIdentityRecord
		configs map[string]VehicleConfigurationRecord
	}
	families := map[string]*family{}
	canonicalRows := make([]VehicleIdentityRow, 0, len(rows))
	for _, row := range rows {
		year := normalizedVehicleYear(row.Year)
		if year < 1886 || year > 2100 || strings.TrimSpace(row.Make) == "" || strings.TrimSpace(row.Model) == "" {
			return nil, nil, ErrVehicleIdentityInvalid
		}
		makeName := titleVehicleWord(row.Make)
		if strings.EqualFold(makeName, "Chevy") {
			makeName = "Chevrolet"
		}
		model := titleVehicleWords(row.Model)
		region := strings.ToUpper(strings.TrimSpace(row.Region))
		drivetrain := normalizeDrivetrain(row.Drivetrain)
		keyParts := []string{slugVehicle(makeName), slugVehicle(model), strconv.Itoa(year)}
		if region != "" {
			keyParts = append(keyParts, slugVehicle(region))
		}
		key := strings.Join(keyParts, "-")
		current, ok := families[key]
		rowConflict := false
		if !ok {
			current = &family{record: VehicleIdentityRecord{VehicleIDKey: key, Year: year, Make: makeName, Model: model, Region: region, Drivetrain: drivetrain}, configs: map[string]VehicleConfigurationRecord{}}
			families[key] = current
		} else if current.record.Drivetrain != "" && drivetrain != "" && current.record.Drivetrain != drivetrain {
			current.record.Conflicts = append(current.record.Conflicts, map[string]string{"field": "drivetrain", "existing": current.record.Drivetrain, "incoming": drivetrain})
			rowConflict = true
		} else if current.record.Drivetrain == "" {
			current.record.Drivetrain = drivetrain
		}
		if current.record.BodyStyle != "" && row.BodyStyle != "" && current.record.BodyStyle != titleVehicleWords(row.BodyStyle) {
			current.record.Conflicts = append(current.record.Conflicts, map[string]string{"field": "body_style", "existing": current.record.BodyStyle, "incoming": titleVehicleWords(row.BodyStyle)})
			rowConflict = true
		} else if current.record.BodyStyle == "" {
			current.record.BodyStyle = titleVehicleWords(row.BodyStyle)
		}
		configKey := key
		if strings.TrimSpace(row.Trim) != "" {
			configKey += "-trim-" + slugVehicle(row.Trim)
		}
		if row.EngineDisplacementL != nil {
			configKey += "-engine-" + strings.ReplaceAll(strconv.FormatFloat(*row.EngineDisplacementL, 'f', 1, 64), ".", "-") + "l"
		}
		if !rowConflict {
			if _, exists := current.configs[configKey]; !exists {
				current.configs[configKey] = VehicleConfigurationRecord{ConfigurationKey: configKey, Trim: strings.TrimSpace(row.Trim), EngineDisplacementL: row.EngineDisplacementL, Drivetrain: current.record.Drivetrain}
			}
		}
		canonicalRows = append(canonicalRows, VehicleIdentityRow{Year: year, Make: makeName, Model: model, Region: region, BodyStyle: current.record.BodyStyle, Trim: strings.TrimSpace(row.Trim), Drivetrain: drivetrain, EngineDisplacementL: row.EngineDisplacementL})
	}
	keys := make([]string, 0, len(families))
	for key := range families {
		keys = append(keys, key)
	}
	sort.Strings(keys)
	result := make([]VehicleIdentityRecord, 0, len(keys))
	for _, key := range keys {
		current := families[key]
		configKeys := make([]string, 0, len(current.configs))
		for configKey := range current.configs {
			configKeys = append(configKeys, configKey)
		}
		sort.Strings(configKeys)
		for _, configKey := range configKeys {
			config := current.configs[configKey]
			config.Drivetrain = current.record.Drivetrain
			current.record.Configurations = append(current.record.Configurations, config)
		}
		if len(current.record.Conflicts) > 0 {
			current.record.Status = "needs_review"
		} else {
			current.record.Status = "resolved"
		}
		result = append(result, current.record)
	}
	return result, canonicalRows, nil
}

func normalizedVehicleYear(value any) int {
	switch raw := value.(type) {
	case int:
		return normalizeTwoDigitYear(raw)
	case float64:
		return normalizeTwoDigitYear(int(raw))
	case string:
		parsed, err := strconv.Atoi(strings.TrimSpace(raw))
		if err != nil {
			return 0
		}
		return normalizeTwoDigitYear(parsed)
	default:
		return 0
	}
}
func normalizeTwoDigitYear(year int) int {
	if year >= 0 && year < 100 {
		if year <= 30 {
			return year + 2000
		}
		return year + 1900
	}
	return year
}
func normalizeDrivetrain(value string) string {
	normalized := strings.ToUpper(strings.NewReplacer(" ", "", "-", "", "_", "").Replace(strings.TrimSpace(value)))
	switch normalized {
	case "4X2":
		return "2WD"
	case "4X4":
		return "4WD"
	case "AWD", "FWD", "RWD", "2WD", "4WD":
		return normalized
	default:
		return normalized
	}
}
func titleVehicleWord(value string) string {
	value = strings.TrimSpace(value)
	if value == "" {
		return ""
	}
	return strings.ToUpper(value[:1]) + strings.ToLower(value[1:])
}
func titleVehicleWords(value string) string {
	words := strings.Fields(strings.TrimSpace(value))
	for i, word := range words {
		words[i] = titleVehicleWord(word)
	}
	return strings.Join(words, " ")
}
func slugVehicle(value string) string {
	value = strings.ToLower(strings.TrimSpace(value))
	var b strings.Builder
	lastDash := false
	for _, r := range value {
		if (r >= 'a' && r <= 'z') || (r >= '0' && r <= '9') {
			b.WriteRune(r)
			lastDash = false
		} else if !lastDash && b.Len() > 0 {
			b.WriteByte('-')
			lastDash = true
		}
	}
	return strings.Trim(b.String(), "-")
}
func sortedStrings(values map[string]bool) []string {
	result := make([]string, 0, len(values))
	for value := range values {
		result = append(result, value)
	}
	sort.Strings(result)
	return result
}
func sortedInts(values map[int]bool) []int {
	result := make([]int, 0, len(values))
	for value := range values {
		result = append(result, value)
	}
	sort.Ints(result)
	return result
}
func sortedFloats(values map[float64]bool) []float64 {
	result := make([]float64, 0, len(values))
	for value := range values {
		result = append(result, value)
	}
	sort.Float64s(result)
	return result
}
