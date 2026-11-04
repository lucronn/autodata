package main

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"
)

func TestWorkshopBrowserTimingSelection(t *testing.T) {
	timing, err := loadWorkshopBrowserTiming("../../scripts/dev/fixtures/workshop_customer/timing.json")
	if err != nil {
		t.Fatal(err)
	}
	if workshopBrowserFixtureLifetime(false, timing) != 4800*time.Second {
		t.Fatal("DTO envelope")
	}
	if workshopBrowserFixtureLifetime(true, timing) != 4400*time.Second {
		t.Fatal("API envelope changed")
	}
	if len(timing.SHA256) != 64 {
		t.Fatal("missing byte hash")
	}
}
func TestWorkshopBrowserTimingRejectsInvalid(t *testing.T) {
	raw, err := os.ReadFile("../../scripts/dev/fixtures/workshop_customer/timing.json")
	if err != nil {
		t.Fatal(err)
	}
	for _, body := range []string{`{}`, strings.Replace(string(raw), `"version": "v1"`, `"version": "v2"`, 1), strings.Replace(string(raw), `"worker_hard_seconds": 4380`, `"worker_hard_seconds": true`, 1), strings.Replace(string(raw), `"dto_fixture_seconds": 4800`, `"dto_fixture_seconds": 4640`, 1), strings.Replace(string(raw), `"version": "v1"`, `"version": "v1", "version": "v1"`, 1)} {
		path := filepath.Join(t.TempDir(), "timing.json")
		if err := os.WriteFile(path, []byte(body), 0600); err != nil {
			t.Fatal(err)
		}
		if _, err := loadWorkshopBrowserTiming(path); err == nil {
			t.Fatal("invalid timing accepted")
		}
	}
}
func TestWorkshopBrowserFixtureDeadlineTerminal(t *testing.T) {
	for _, expired := range []bool{true, false} {
		stopped, deadline := make(chan struct{}, 1), make(chan time.Time, 1)
		if expired {
			deadline <- time.Time{}
		} else {
			stopped <- struct{}{}
		}
		if got := workshopBrowserFixtureEnded(stopped, deadline); got != expired {
			t.Fatal("terminal event lost")
		}
	}
}
