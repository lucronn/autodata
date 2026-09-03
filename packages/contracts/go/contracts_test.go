package contracts

import "testing"

func TestGeneratedBindingsExposeDatasetReadContract(t *testing.T) {
	if SchemaVersion != 1 {
		t.Fatalf("schema version = %d, want 1", SchemaVersion)
	}
	want := []string{"dataset_id", "revision_id", "availability", "source_watermark", "sections"}
	if !sameStrings(DatasetReadRequiredFields, want) {
		t.Fatalf("dataset required fields = %#v, want %#v", DatasetReadRequiredFields, want)
	}
}

func TestGeneratedBindingsExposeSupportingContractTypes(t *testing.T) {
	_ = DatasetRequest{}
	_ = Entitlement{}
	_ = Evidence{}
	_ = Feedback{}
	_ = Error{}
	_ = KnowledgeSearchResponse{}
	_ = KnowledgeResult{}
	_ = KnowledgeArticle{}
	_ = KnowledgeProcedure{}
	_ = KnowledgeEvidence{}
}

func TestGeneratedBindingsExposeLifecycleAndEventSubjects(t *testing.T) {
	if !contains(DatasetAvailabilityValues, "viewable") {
		t.Fatal("dataset availability must include viewable")
	}
	if !contains(SectionStatusValues, "needs_review") {
		t.Fatal("section status must include needs_review")
	}
	if !contains(EventSubjects, "dataset.section.published") {
		t.Fatal("event subjects must include section publication")
	}
	if !contains(KnowledgeResultKindValues, "article") || !contains(KnowledgeResultKindValues, "procedure") {
		t.Fatal("knowledge result kinds must include article and procedure")
	}
	if !contains(EntitlementStatusValues, "active") {
		t.Fatal("entitlement statuses must include active")
	}
	if !contains(FeedbackCategoryValues, "correction") {
		t.Fatal("feedback categories must include correction")
	}
	if !contains(ErrorCodeValues, "INVALID_EVIDENCE") {
		t.Fatal("error codes must include invalid evidence")
	}
}

func sameStrings(left, right []string) bool {
	if len(left) != len(right) {
		return false
	}
	for index := range left {
		if left[index] != right[index] {
			return false
		}
	}
	return true
}

func contains(values []string, want string) bool {
	for _, value := range values {
		if value == want {
			return true
		}
	}
	return false
}
