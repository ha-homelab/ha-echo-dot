package main

import "testing"

func TestTimingIncludesWarmupAndRefractory(t *testing.T) {
	// A continuously high output should fire at 3000ms and 4100ms,
	// not every inference/poll and not during excluded warmup.
	scores := []score{{Invocation: 1, Raw: 255, Average: 1}}
	events, first := echoTimedEvents(scores, 3, 4500*16, 3000, .9)
	if events != 2 || first != 3000 {
		t.Fatalf("got %d events first=%d; want 2 first=3000", events, first)
	}
}

func TestTimingDoesNotEmitBeforeFirstInference(t *testing.T) {
	events, _ := echoTimedEvents(nil, 3, 4000*16, 3000, .9)
	if events != 0 {
		t.Fatalf("missing inference produced %d events", events)
	}
}
