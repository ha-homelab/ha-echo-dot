package main

import (
	"crypto/sha256"
	"encoding/binary"
	"encoding/json"
	"fmt"
	"io"
	"math"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"time"

	"github.com/zserge/microwakeword/audiofrontend"
	"github.com/zserge/microwakeword/interpreter"
)

type batchClip struct {
	ID         string `json:"id"`
	Label      string `json:"label"`
	WAV        string `json:"wav"`
	PCM        string `json:"pcm"`
	LeadingMs  int    `json:"leading_ms"`
	TrailingMs int    `json:"trailing_ms"`
}
type thresholdCounts struct {
	Threshold             float64 `json:"threshold"`
	PositiveHits          int     `json:"positive_clips_detected"`
	NegativeHits          int     `json:"negative_clips_detected"`
	NegativeRuns          int     `json:"negative_threshold_runs"`
	NegativeEvents        int     `json:"negative_echo_timing_events"`
	Recall                float64 `json:"positive_clip_recall"`
	NegativeFraction      float64 `json:"negative_clip_hit_fraction"`
	NegativeEventsPerHour float64 `json:"negative_events_per_source_hour"`
}
type clipThreshold struct {
	Threshold    float64 `json:"threshold"`
	Runs         int     `json:"threshold_runs"`
	Events       int     `json:"echo_timing_events"`
	FirstEventMs int     `json:"first_event_ms"`
}

func runBatch(manifestPath, outPath, gridText string, data []byte, interp *interpreter.Interpreter, stride, window int, start time.Time) error {
	if outPath == "" {
		return fmt.Errorf("-manifest requires -batch-out")
	}
	var counts []thresholdCounts
	previous := -1.0
	for _, s := range strings.Split(gridText, ",") {
		v, err := strconv.ParseFloat(strings.TrimSpace(s), 64)
		if err != nil || math.IsNaN(v) || v < 0 || v > 1 || v <= previous {
			return fmt.Errorf("thresholds must be strictly increasing numbers in [0,1]")
		}
		counts = append(counts, thresholdCounts{Threshold: v})
		previous = v
	}
	mf, err := os.Open(manifestPath)
	if err != nil {
		return err
	}
	defer mf.Close()
	of, err := os.OpenFile(outPath, os.O_CREATE|os.O_WRONLY|os.O_EXCL, 0600)
	if err != nil {
		return err
	}
	defer of.Close()
	if err = of.Chmod(0600); err != nil {
		return err
	}
	decoder := json.NewDecoder(mf)
	decoder.DisallowUnknownFields()
	enc := json.NewEncoder(of)
	seen := map[string]bool{}
	positives, negatives, total := 0, 0, 0
	positiveSeconds, negativeSeconds, paddingSeconds := 0.0, 0.0, 0.0
	for {
		var row batchClip
		if err = decoder.Decode(&row); err == io.EOF {
			break
		}
		if err != nil {
			return fmt.Errorf("manifest row %d: %w", total+1, err)
		}
		if row.ID == "" || seen[row.ID] {
			return fmt.Errorf("row %d needs a unique nonempty id", total+1)
		}
		seen[row.ID] = true
		if row.Label != "positive" && row.Label != "negative" {
			return fmt.Errorf("row %s label must be positive or negative", row.ID)
		}
		if (row.WAV == "") == (row.PCM == "") {
			return fmt.Errorf("row %s needs exactly one wav or pcm path", row.ID)
		}
		if row.LeadingMs < 0 || row.TrailingMs < 0 || row.LeadingMs > 10000 || row.TrailingMs > 10000 {
			return fmt.Errorf("row %s invalid padding milliseconds", row.ID)
		}
		path := row.WAV
		if path == "" {
			path = row.PCM
		}
		if !filepath.IsAbs(path) {
			path = filepath.Join(filepath.Dir(manifestPath), path)
		}
		var pcm []int16
		if row.WAV != "" {
			pcm, err = readWAV(path)
		} else {
			var b []byte
			b, err = os.ReadFile(path)
			if err == nil {
				if len(b)%2 != 0 {
					return fmt.Errorf("row %s odd PCM byte count", row.ID)
				}
				pcm = make([]int16, len(b)/2)
				for i := range pcm {
					pcm[i] = int16(binary.LittleEndian.Uint16(b[i*2:]))
				}
			}
		}
		if err != nil {
			return fmt.Errorf("row %s audio: %w", row.ID, err)
		}
		originalSamples := len(pcm)
		if originalSamples < 480 {
			return fmt.Errorf("row %s source is shorter than 30ms", row.ID)
		}
		sourceSeconds := float64(originalSamples) / 16000
		if row.Label == "positive" {
			positives++
			positiveSeconds += sourceSeconds
		} else {
			negatives++
			negativeSeconds += sourceSeconds
		}
		paddingSeconds += float64(row.LeadingMs+row.TrailingMs) / 1000
		if row.LeadingMs+row.TrailingMs > 0 {
			padded := make([]int16, row.LeadingMs*16+len(pcm)+row.TrailingMs*16)
			copy(padded[row.LeadingMs*16:], pcm)
			pcm = padded
		}
		fe := audiofrontend.New(audiofrontend.DefaultConfig(10))
		frames := fe.ProcessAllInt8(pcm)
		interp.Reset()
		scores, e := runFrames(interp, frames, stride, window)
		if e != nil {
			return fmt.Errorf("row %s: %w", row.ID, e)
		}
		if len(scores) == 0 {
			return fmt.Errorf("row %s too short for stride", row.ID)
		}
		maxAvg := 0.0
		maxMs := 0
		for _, s := range scores {
			if 30+(s.Invocation*stride-1)*10 >= row.LeadingMs && s.Average > maxAvg {
				maxAvg = s.Average
				maxMs = 30 + (s.Invocation*stride-1)*10
			}
		}
		ct := make([]clipThreshold, len(counts))
		for j := range counts {
			cutoff := counts[j].Threshold
			runs := 0
			above := false
			for _, s := range scores {
				if 30+(s.Invocation*stride-1)*10 < row.LeadingMs {
					continue
				}
				now := s.Average >= cutoff
				if now && !above {
					runs++
				}
				above = now
			}
			events, first := echoTimedEvents(scores, stride, len(pcm), row.LeadingMs, cutoff)
			ct[j] = clipThreshold{cutoff, runs, events, first}
			if row.Label == "positive" {
				if events > 0 {
					counts[j].PositiveHits++
				}
			} else {
				if events > 0 {
					counts[j].NegativeHits++
				}
				counts[j].NegativeRuns += runs
				counts[j].NegativeEvents += events
			}
		}
		r := map[string]any{"id": row.ID, "label": row.Label, "source_audio_seconds": sourceSeconds, "score_after_ms": row.LeadingMs, "leading_zero_padding_ms": row.LeadingMs, "trailing_zero_padding_ms": row.TrailingMs, "feature_frames": len(frames), "invocations": len(scores), "max_sliding_average": maxAvg, "peak_frame_end_ms": maxMs, "thresholds": ct}
		if err = enc.Encode(r); err != nil {
			return err
		}
		total++
		if total%25 == 0 {
			fmt.Fprintf(os.Stderr, "evaluated %d clips, %.1fs source audio, %.1fs elapsed\n", total, positiveSeconds+negativeSeconds, time.Since(start).Seconds())
		}
	}
	if total == 0 {
		return fmt.Errorf("empty manifest")
	}
	for j := range counts {
		if positives > 0 {
			counts[j].Recall = float64(counts[j].PositiveHits) / float64(positives)
		}
		if negatives > 0 {
			counts[j].NegativeFraction = float64(counts[j].NegativeHits) / float64(negatives)
		}
		if negativeSeconds > 0 {
			counts[j].NegativeEventsPerHour = float64(counts[j].NegativeEvents) * 3600 / negativeSeconds
		}
	}
	summary := map[string]any{"runtime": runtimePin, "model_sha256": fmt.Sprintf("%x", sha256.Sum256(data)), "manifest": manifestPath, "per_clip_results": outPath, "clips": total, "positive_clips": positives, "negative_clips": negatives, "positive_source_seconds": positiveSeconds, "negative_source_seconds": negativeSeconds, "negative_source_hours": negativeSeconds / 3600, "added_padding_seconds": paddingSeconds, "feature_step_ms": 10, "sliding_window": window, "thresholds": counts, "frontend_state_reset": "once per manifest row, never between frames within a row", "timing_model": "20ms microphone poll, last available exact Go score, 300ms hold then 800ms refractory; virtual audio clock; includes startup averages before the full window", "note": "Offline model events, not measured HA activations. Separate negative clips are aggregate speech hours, not a continuous acoustic soak. Leading padding is warm-up excluded from maxima/events but fed to the streaming state. Padding is digital zero, not ambient noise. Row labels determine clip recall; no speech-onset timing labels are used.", "elapsed_seconds": time.Since(start).Seconds()}
	je := json.NewEncoder(os.Stdout)
	je.SetIndent("", "  ")
	return je.Encode(summary)
}

// EchoLocal 0.0.8 checks the last microBackend score on each 20ms mic frame.
// This reproduces hold/refractory timing with a virtual audio clock, not HA voice lifecycle.
func echoTimedEvents(scores []score, stride, samples, scoreAfterMs int, cutoff float64) (int, int) {
	idx := 0
	avg := 0.0
	holding := false
	holdEnds, quietUntil := 0, 0
	events, first := 0, -1
	for t := 20; t <= samples/16; t += 20 {
		for idx < len(scores) && 30+(scores[idx].Invocation*stride-1)*10 <= t {
			avg = scores[idx].Average
			idx++
		}
		if t < scoreAfterMs {
			continue
		}
		if t < quietUntil {
			continue
		}
		if holding {
			if t < holdEnds {
				continue
			}
			holding = false
			quietUntil = t + 800
			continue
		}
		if avg < cutoff {
			continue
		}
		events++
		if first < 0 {
			first = t
		}
		holding = true
		holdEnds = t + 300
	}
	return events, first
}
