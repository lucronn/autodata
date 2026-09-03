package main

import (
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"sort"
	"strconv"
	"strings"
	"unicode"

	"github.com/lucronn/autodata/packages/contracts/go"
)

const (
	knowledgeDefaultLimit = 10
	knowledgeMaxLimit     = 50
)

func (s *Server) searchKnowledge(response http.ResponseWriter, request *http.Request, principal Principal) {
	datasetID, ok := datasetPathValue(request)
	if !ok {
		writeAPIError(response, request, http.StatusUnprocessableEntity, "INVALID_REQUEST", "dataset ID is required", false)
		return
	}
	query := strings.TrimSpace(request.URL.Query().Get("q"))
	if query == "" {
		writeAPIError(response, request, http.StatusUnprocessableEntity, "INVALID_REQUEST", "knowledge query is required", false)
		return
	}
	kind := strings.ToLower(strings.TrimSpace(request.URL.Query().Get("kind")))
	if kind == "" {
		kind = "all"
	}
	if kind != "article" && kind != "procedure" && kind != "all" {
		writeAPIError(response, request, http.StatusUnprocessableEntity, "INVALID_REQUEST", "kind must be article, procedure, or all", false)
		return
	}
	limit := knowledgeDefaultLimit
	if rawLimit := strings.TrimSpace(request.URL.Query().Get("limit")); rawLimit != "" {
		parsed, err := strconv.Atoi(rawLimit)
		if err != nil || parsed < 1 || parsed > knowledgeMaxLimit {
			writeAPIError(response, request, http.StatusUnprocessableEntity, "INVALID_REQUEST", "limit must be between 1 and 50", false)
			return
		}
		limit = parsed
	}
	fallback, err := parseKnowledgeFallback(request.URL.Query().Get("fallback"))
	if err != nil {
		writeAPIError(response, request, http.StatusUnprocessableEntity, "INVALID_REQUEST", err.Error(), false)
		return
	}
	revisionID := strings.TrimSpace(request.URL.Query().Get("revision_id"))
	result, err := s.projections.SearchKnowledge(datasetID, query, kind, limit, revisionID, principal)
	if !s.writeProjectionError(response, request, err) {
		return
	}
	if !fallback || len(result.Results) > 0 {
		if fallback {
			result.FallbackStatus = "fetched"
		}
		writeJSON(response, http.StatusOK, result)
		return
	}
	event, err := newKnowledgeFallbackEvent(request, result, query, kind, limit)
	if err != nil {
		log.Printf("build knowledge fallback event %s: %v", requestIDFrom(request), err)
		writeAPIError(response, request, http.StatusInternalServerError, "INVALID_REQUEST", "knowledge fallback request could not be created", true)
		return
	}
	if err := s.knowledgeFallbackPublisher.Publish(request.Context(), event); err != nil {
		log.Printf("publish knowledge fallback event %s: %v", requestIDFrom(request), err)
		writeAPIError(response, request, http.StatusInternalServerError, "INVALID_REQUEST", "knowledge fallback request could not be published", true)
		return
	}
	result.FallbackStatus = "pending"
	result.FallbackRequestID = event.EventID
	writeJSON(response, http.StatusAccepted, result)
}

func parseKnowledgeFallback(raw string) (bool, error) {
	switch strings.TrimSpace(raw) {
	case "":
		return false, nil
	case "true":
		return true, nil
	case "false":
		return false, nil
	default:
		return false, fmt.Errorf("fallback must be true or false")
	}
}

type knowledgeCandidate struct {
	result contracts.KnowledgeResult
}

func searchKnowledgeRevision(
	datasetID string,
	revision DatasetRevisionRecord,
	sections []contracts.DatasetSection,
	evidence map[string]EvidenceRecord,
	query, kind string,
	limit int,
) KnowledgeSearchResponse {
	response := KnowledgeSearchResponse{
		DatasetID:       datasetID,
		RevisionID:      revision.RevisionID,
		Availability:    revision.Availability,
		SourceWatermark: revision.SourceWatermark,
		Sections:        sections,
		Results:         []contracts.KnowledgeResult{},
	}
	if vehicle, ok := revision.Data["vehicle_identity"].(map[string]any); ok {
		response.VehicleIdentity = vehicle
	} else if vehicleKey := firstKnowledgeString(revision.Data, "vehicle_key"); vehicleKey != "" {
		response.VehicleIdentity = map[string]any{"vehicle_key": vehicleKey}
	}
	queryTokens := knowledgeTokens(query)
	if len(queryTokens) == 0 || revision.Data == nil {
		return response
	}

	candidates := make([]knowledgeCandidate, 0)
	if kind == "all" || kind == "article" {
		for _, raw := range knowledgeRecords(revision.Data["articles"]) {
			candidate, ok := articleCandidate(raw, queryTokens, evidence, revision.RevisionID)
			if ok {
				candidates = append(candidates, knowledgeCandidate{result: candidate})
			}
		}
	}
	if kind == "all" || kind == "procedure" {
		for _, raw := range procedureRecords(revision.Data["procedures"]) {
			candidate, ok := procedureCandidate(raw, queryTokens, evidence, revision.RevisionID)
			if ok {
				candidates = append(candidates, knowledgeCandidate{result: candidate})
			}
		}
	}
	sort.SliceStable(candidates, func(i, j int) bool {
		left, right := candidates[i].result, candidates[j].result
		if left.Score != right.Score {
			return left.Score > right.Score
		}
		if left.Kind != right.Kind {
			return left.Kind < right.Kind
		}
		return left.ID < right.ID
	})
	if limit > len(candidates) {
		limit = len(candidates)
	}
	for _, candidate := range candidates[:limit] {
		response.Results = append(response.Results, candidate.result)
	}
	return response
}

func articleCandidate(record map[string]any, queryTokens []string, evidence map[string]EvidenceRecord, revisionID string) (contracts.KnowledgeResult, bool) {
	articleID := firstKnowledgeString(record, "article_id", "articleId", "id")
	if articleID == "" {
		return contracts.KnowledgeResult{}, false
	}
	searchText := strings.Join([]string{
		firstKnowledgeString(record, "article_id", "articleId", "id"),
		firstKnowledgeString(record, "article_key"),
		firstKnowledgeString(record, "bucket"),
		firstKnowledgeString(record, "title"),
		firstKnowledgeString(record, "bulletin_number", "bulletinNumber"),
		firstKnowledgeString(record, "release_date", "releaseDate"),
		firstKnowledgeString(record, "body", "articleBody", "content"),
		knowledgeJSONText(record["steps"]),
	}, " ")
	score := knowledgeScore(queryTokens, searchText)
	if score == 0 {
		return contracts.KnowledgeResult{}, false
	}
	article := &contracts.KnowledgeArticle{
		ArticleID:      articleID,
		ArticleKey:     firstKnowledgeString(record, "article_key"),
		Bucket:         firstKnowledgeString(record, "bucket"),
		Title:          firstKnowledgeString(record, "title"),
		BulletinNumber: firstKnowledgeString(record, "bulletin_number", "bulletinNumber"),
		ReleaseDate:    firstKnowledgeString(record, "release_date", "releaseDate"),
		Body:           firstKnowledgeString(record, "body", "articleBody", "content"),
		Steps:          knowledgeSlice(record["steps"]),
	}
	return contracts.KnowledgeResult{
		Kind:     "article",
		ID:       articleID,
		Score:    score,
		Article:  article,
		Evidence: knowledgeEvidence(record, evidence, revisionID),
	}, true
}

func procedureCandidate(record map[string]any, queryTokens []string, evidence map[string]EvidenceRecord, revisionID string) (contracts.KnowledgeResult, bool) {
	excerpt := firstKnowledgeString(record, "text", "excerpt", "extracted_text", "content")
	if excerpt == "" {
		return contracts.KnowledgeResult{}, false
	}
	section := firstKnowledgeString(record, "section")
	if section == "" {
		section = "procedures"
	}
	score := knowledgeScore(queryTokens, strings.Join([]string{section, excerpt, knowledgeJSONText(record["matched_terms"])}, " "))
	if score == 0 {
		return contracts.KnowledgeResult{}, false
	}
	evidenceID := firstKnowledgeString(record, "source_evidence_id", "evidence_id")
	procedureID := firstKnowledgeString(record, "procedure_id", "id")
	if procedureID == "" {
		procedureID = "procedure:" + evidenceID
	}
	procedure := &contracts.KnowledgeProcedure{
		ProcedureID:  procedureID,
		Section:      section,
		Excerpt:      excerpt,
		MatchedTerms: knowledgeStringSlice(record["matched_terms"]),
	}
	return contracts.KnowledgeResult{
		Kind:      "procedure",
		ID:        procedureID,
		Score:     score,
		Procedure: procedure,
		Evidence:  knowledgeEvidence(record, evidence, revisionID),
	}, true
}

func knowledgeEvidence(record map[string]any, records map[string]EvidenceRecord, revisionID string) []contracts.KnowledgeEvidence {
	ids := knowledgeStringSlice(record["evidence_ids"])
	if len(ids) == 0 {
		if id := firstKnowledgeString(record, "evidence_id", "source_evidence_id"); id != "" {
			ids = []string{id}
		}
	}
	result := make([]contracts.KnowledgeEvidence, 0, len(ids))
	for _, id := range ids {
		if existing, ok := records[id]; ok {
			if existing.DatasetRevisionID != nil {
				if *existing.DatasetRevisionID != revisionID {
					continue
				}
				if existing.ReviewerState != "" && existing.ReviewerState != "approved" {
					continue
				}
				result = append(result, contracts.KnowledgeEvidence{
					EvidenceID:       id,
					Locator:          knowledgeFirstNonEmpty(existing.Locator, firstKnowledgeString(record, "content_locator", "locator")),
					SourceSnapshotID: existing.SourceSnapshotID,
					ArtifactKey:      knowledgeFirstNonEmpty(existing.ArtifactKey, firstKnowledgeString(record, "artifact_key")),
					SourceURI:        firstKnowledgeString(record, "source_uri"),
					SourceVersion:    firstKnowledgeString(record, "source_version"),
					ExtractedText:    existing.ExtractedText,
					Confidence:       existing.Confidence,
				})
				continue
			}
			if existing.ReviewerState != "" && existing.ReviewerState != "approved" {
				continue
			}
		}
		result = append(result, contracts.KnowledgeEvidence{
			EvidenceID:       id,
			Locator:          firstKnowledgeString(record, "content_locator", "locator"),
			SourceSnapshotID: firstKnowledgeString(record, "source_snapshot_id", "_source_snapshot_id"),
			ArtifactKey:      firstKnowledgeString(record, "artifact_key"),
			SourceURI:        firstKnowledgeString(record, "source_uri"),
			SourceVersion:    firstKnowledgeString(record, "source_version"),
			Confidence:       firstKnowledgeNumber(record, "confidence"),
		})
	}
	return result
}

func knowledgeFirstNonEmpty(values ...string) string {
	for _, value := range values {
		if strings.TrimSpace(value) != "" {
			return strings.TrimSpace(value)
		}
	}
	return ""
}

func knowledgeRecords(value any) []map[string]any {
	var result []map[string]any
	switch records := value.(type) {
	case []any:
		for _, item := range records {
			if record, ok := item.(map[string]any); ok {
				result = append(result, record)
			}
		}
	case []map[string]any:
		result = append(result, records...)
	}
	return result
}

func procedureRecords(value any) []map[string]any {
	if record, ok := value.(map[string]any); ok {
		rows := knowledgeRecords(record["records"])
		sourceSnapshotID := firstKnowledgeString(record, "source_snapshot_id")
		if sourceSnapshotID != "" {
			for _, row := range rows {
				if firstKnowledgeString(row, "source_snapshot_id") == "" {
					row["_source_snapshot_id"] = sourceSnapshotID
				}
			}
		}
		return rows
	}
	return knowledgeRecords(value)
}

func knowledgeTokens(value string) []string {
	seen := make(map[string]struct{})
	var tokens []string
	for _, token := range strings.FieldsFunc(strings.ToLower(value), func(r rune) bool { return !unicode.IsLetter(r) && !unicode.IsDigit(r) }) {
		if _, ok := seen[token]; ok {
			continue
		}
		seen[token] = struct{}{}
		tokens = append(tokens, token)
	}
	return tokens
}

func knowledgeScore(queryTokens []string, text string) float64 {
	textTokens := make(map[string]struct{})
	for _, token := range knowledgeTokens(text) {
		textTokens[token] = struct{}{}
	}
	matched := 0
	for _, token := range queryTokens {
		if _, ok := textTokens[token]; ok {
			matched++
		}
	}
	return float64(matched) / float64(len(queryTokens))
}

func firstKnowledgeString(record map[string]any, keys ...string) string {
	for _, key := range keys {
		if value, ok := record[key].(string); ok && strings.TrimSpace(value) != "" {
			return strings.TrimSpace(value)
		}
	}
	return ""
}

func firstKnowledgeNumber(record map[string]any, keys ...string) float64 {
	for _, key := range keys {
		switch value := record[key].(type) {
		case float64:
			return value
		case float32:
			return float64(value)
		case int:
			return float64(value)
		}
	}
	return 0
}

func knowledgeStringSlice(value any) []string {
	var result []string
	switch values := value.(type) {
	case []any:
		for _, value := range values {
			if text, ok := value.(string); ok && strings.TrimSpace(text) != "" {
				result = append(result, strings.TrimSpace(text))
			}
		}
	case []string:
		for _, value := range values {
			if strings.TrimSpace(value) != "" {
				result = append(result, strings.TrimSpace(value))
			}
		}
	}
	return result
}

func knowledgeSlice(value any) []any {
	if values, ok := value.([]any); ok {
		return values
	}
	if values, ok := value.([]string); ok {
		result := make([]any, len(values))
		for index, value := range values {
			result[index] = value
		}
		return result
	}
	return nil
}

func knowledgeJSONText(value any) string {
	if value == nil {
		return ""
	}
	encoded, err := json.Marshal(value)
	if err != nil {
		return fmt.Sprint(value)
	}
	return string(encoded)
}
