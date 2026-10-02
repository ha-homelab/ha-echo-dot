// Offline compatibility gate for the exact microWakeWord runtime in EchoLocal 0.0.8.
// This program never contacts or changes an Echo or Home Assistant.
package main

import (
	"crypto/sha256"
	"encoding/binary"
	"encoding/csv"
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"math"
	"os"
	"sort"
	"strconv"
	"time"

	mww "github.com/zserge/microwakeword"
	"github.com/zserge/microwakeword/audiofrontend"
	"github.com/zserge/microwakeword/interpreter"
	"github.com/zserge/microwakeword/model"
)

const runtimePin = "github.com/zserge/microwakeword@v0.0.0-20260330234603-bfaf3840114e"

var supported = map[int]bool{129: true, 142: true, 143: true, 144: true, 22: true, 2: true, 45: true, 3: true, 4: true, 9: true, 14: true, 114: true, 102: true}

type score struct {
	Invocation int     `json:"invocation"`
	Raw        uint8   `json:"raw_uint8"`
	Average    float64 `json:"sliding_average"`
}

func main() {
	defer func() {
		if r := recover(); r != nil {
			fmt.Fprintln(os.Stderr, "VALIDATION FAILED (parser/runtime panic):", r)
			os.Exit(1)
		}
	}()
	if err := run(); err != nil {
		fmt.Fprintln(os.Stderr, "VALIDATION FAILED:", err)
		os.Exit(1)
	}
}
func run() error {
	manifestPath := flag.String("manifest", "", "optional JSONL batch manifest; rows: id,label,wav or pcm,leading_ms,trailing_ms")
	batchOut := flag.String("batch-out", "", "required with -manifest: private per-clip JSONL results")
	gridText := flag.String("thresholds", "0.50,0.60,0.65,0.70,0.75,0.80,0.85,0.90,0.92,0.95,0.97,0.99", "batch threshold grid")
	modelPath := flag.String("model", "", "required .tflite model")
	wavPath := flag.String("wav", "", "optional PCM16 mono 16000Hz RIFF WAV")
	featuresIn := flag.String("features-in", "", "optional row-major int8 frames, 40 bytes/frame, no header")
	featuresOut := flag.String("features-out", "", "optional Go frontend int8 features output")
	rawOut := flag.String("raw-features-out", "", "optional Go frontend uint16 little-endian features output")
	scoresOut := flag.String("scores-out", "", "optional direct Invoke CSV output")
	stepMs := flag.Int("step-ms", 10, "frontend hop; this training workflow requires 10ms")
	window := flag.Int("window", 5, "sliding average window, like EchoLocal model manifest")
	threshold := flag.Float64("threshold", 0.85, "score reporting threshold; does not stop inference")
	flag.Parse()
	if *modelPath == "" || flag.NArg() != 0 {
		return errors.New("pass -model MODEL.tflite and optional -wav AUDIO.wav")
	}
	if *stepMs != 10 || *window < 1 || *threshold < 0 || *threshold > 1 {
		return errors.New("requires step-ms=10, window>=1, threshold in [0,1]")
	}
	if *manifestPath != "" && (*wavPath != "" || *featuresIn != "" || *featuresOut != "" || *rawOut != "" || *scoresOut != "") {
		return errors.New("-manifest cannot be mixed with single-clip input/output flags")
	}
	if *wavPath != "" && *featuresIn != "" {
		return errors.New("-wav and -features-in are mutually exclusive")
	}
	if *rawOut != "" && *wavPath == "" {
		return errors.New("-raw-features-out requires -wav")
	}
	start := time.Now()
	data, err := os.ReadFile(*modelPath)
	if err != nil {
		return err
	}
	if len(data) < 8 || string(data[4:8]) != "TFL3" {
		return errors.New("missing TFL3 FlatBuffer identifier")
	}
	m, err := model.Parse(data)
	if err != nil {
		return err
	}
	ops, err := checkModel(m)
	if err != nil {
		return err
	}
	sg := m.Subgraphs[0]
	in, out := sg.Tensors[sg.Inputs[0]], sg.Tensors[sg.Outputs[0]]
	stride := in.Shape[1]
	interp, err := interpreter.New(m)
	if err != nil {
		return err
	}
	// Exercise initialization and successive resource-state updates; NewDetector alone is insufficient.
	synthetic := make([]int8, stride*40)
	for n := 0; n < 64; n++ {
		for j := range synthetic {
			synthetic[j] = int8((n*37+j*17)%256 - 128)
		}
		if _, err = invoke(interp, synthetic); err != nil {
			return fmt.Errorf("smoke invocation %d: %w", n, err)
		}
	}
	interp.Reset()
	if *manifestPath != "" {
		return runBatch(*manifestPath, *batchOut, *gridText, data, interp, stride, *window, start)
	}
	var pcm []int16
	var frames [][]int8
	var rawFrames [][]uint16
	if *wavPath != "" {
		pcm, err = readWAV(*wavPath)
		if err != nil {
			return err
		}
		fe := audiofrontend.New(audiofrontend.DefaultConfig(*stepMs))
		for offset := 0; offset+480 <= len(pcm); offset += 160 {
			raw := fe.ProcessFrame(pcm[offset : offset+480])
			frame := make([]int8, 40)
			for j, v := range raw {
				q := (int32(v)*256+333)/666 - 128
				if q < -128 {
					q = -128
				}
				if q > 127 {
					q = 127
				}
				frame[j] = int8(q)
			}
			frames = append(frames, frame)
			rawFrames = append(rawFrames, raw)
		}
	} else if *featuresIn != "" {
		b, e := os.ReadFile(*featuresIn)
		if e != nil {
			return e
		}
		if len(b)%40 != 0 {
			return errors.New("features-in length must be a multiple of 40")
		}
		for i := 0; i < len(b); i += 40 {
			frame := make([]int8, 40)
			for j := range frame {
				frame[j] = int8(b[i+j])
			}
			frames = append(frames, frame)
		}
	}
	if (*wavPath != "" || *featuresIn != "") && len(frames) < stride {
		return errors.New("audio/features too short for one complete inference")
	}
	if *featuresOut != "" {
		var b []byte
		for _, f := range frames {
			for _, x := range f {
				b = append(b, byte(x))
			}
		}
		if err = privateWrite(*featuresOut, b); err != nil {
			return err
		}
	}
	if *rawOut != "" {
		b := make([]byte, len(rawFrames)*80)
		for i, f := range rawFrames {
			for j, x := range f {
				binary.LittleEndian.PutUint16(b[(i*40+j)*2:], x)
			}
		}
		if err = privateWrite(*rawOut, b); err != nil {
			return err
		}
	}
	scores, err := runFrames(interp, frames, stride, *window)
	if err != nil {
		return err
	}
	// Verify direct checked Invoke agrees with the public Detector used by EchoLocal.
	if len(scores) > 0 {
		detector, e := mww.NewDetector(mww.Config{ModelPath: *modelPath, ProbabilityCutoff: 1.1, SlidingWindowSize: *window, FeaturesStepMs: *stepMs})
		if e != nil {
			return e
		}
		var observed []score
		detector.OnInference = func(n int, p uint8, a float64) { observed = append(observed, score{n, p, a}) }
		if *wavPath != "" {
			for i := 0; i < len(pcm); i += 160 {
				end := i + 160
				if end > len(pcm) {
					end = len(pcm)
				}
				detector.ProcessAudio(pcm[i:end])
			}
		} else {
			detector.ProcessFeatures(frames)
		}
		if len(observed) != len(scores) {
			return fmt.Errorf("Detector produced %d inferences; direct Invoke produced %d (possible silent runtime failure)", len(observed), len(scores))
		}
		for i := range scores {
			if observed[i].Raw != scores[i].Raw || math.Abs(observed[i].Average-scores[i].Average) > 1e-12 {
				return fmt.Errorf("Detector/direct mismatch at inference %d: %+v vs %+v", i+1, observed[i], scores[i])
			}
		}
	}
	if *scoresOut != "" {
		if err = writeScores(*scoresOut, scores, stride, *stepMs); err != nil {
			return err
		}
	}
	minFeature, maxFeature := 127, -128
	for _, f := range frames {
		for _, q := range f {
			if int(q) < minFeature {
				minFeature = int(q)
			}
			if int(q) > maxFeature {
				maxFeature = int(q)
			}
		}
	}
	maxRaw := 0
	maxAvg := 0.0
	above := 0
	for _, s := range scores {
		if int(s.Raw) > maxRaw {
			maxRaw = int(s.Raw)
		}
		if s.Average > maxAvg {
			maxAvg = s.Average
		}
		if s.Average >= *threshold {
			above++
		}
	}
	report := map[string]any{"compatible_structure_and_invoke": true, "runtime": runtimePin, "model_sha256": fmt.Sprintf("%x", sha256.Sum256(data)), "model_bytes": len(data), "input": in, "output": out, "supported_ops_used": ops, "subgraphs": len(m.Subgraphs), "smoke_invocations": 64, "feature_step_ms": *stepMs, "feature_frames": len(frames), "invocations": len(scores), "unconsumed_trailing_frames": len(frames) % stride, "sliding_window": *window, "threshold": *threshold, "max_raw_uint8": maxRaw, "max_sliding_average": maxAvg, "above_threshold_invocations": above, "elapsed_seconds": time.Since(start).Seconds(), "note": "Runtime compatibility is not acoustic acceptance. Untrained models can pass. Require trained-model TensorFlow parity plus held-out positive and negative audio."}
	if len(frames) > 0 {
		report["detector_direct_parity"] = true
		report["int8_feature_min"] = minFeature
		report["int8_feature_max"] = maxFeature
	}
	if *wavPath != "" {
		report["audio_seconds"] = float64(len(pcm)) / 16000
		report["frontend"] = "exact pinned Go frontend, 30ms window, 10ms hop, 40 channels, 125-7500Hz"
	}
	enc := json.NewEncoder(os.Stdout)
	enc.SetIndent("", "  ")
	return enc.Encode(report)
}
func checkModel(m *model.Model) ([]string, error) {
	if len(m.Subgraphs) == 0 {
		return nil, errors.New("no subgraphs")
	}
	sg := m.Subgraphs[0]
	if len(sg.Inputs) != 1 || len(sg.Outputs) != 1 {
		return nil, errors.New("require exactly one main input and output, internal streaming state")
	}
	in, out := sg.Tensors[sg.Inputs[0]], sg.Tensors[sg.Outputs[0]]
	if in.Type != model.TensorInt8 || len(in.Shape) != 3 || in.Shape[0] != 1 || in.Shape[1] < 1 || in.Shape[2] != 40 {
		return nil, fmt.Errorf("input must be INT8 [1,stride,40], got type=%d shape=%v", in.Type, in.Shape)
	}
	if out.Type != model.TensorUint8 || model.TensorSize(out.Shape) != 1 {
		return nil, fmt.Errorf("output must be single UINT8 score, got type=%d shape=%v", out.Type, out.Shape)
	}
	// Allow small converter calibration rounding (the smoke export is ~1e-5 relative off).
	if err := checkQuant(in, 26.0/255, -128, 2e-5); err != nil {
		return nil, fmt.Errorf("input: %w", err)
	}
	if err := checkQuant(out, 1.0/256, 0, 1e-7); err != nil {
		return nil, fmt.Errorf("output: %w", err)
	}
	seen := map[int]bool{}
	for gi, g := range m.Subgraphs {
		for ti, t := range g.Tensors {
			if t.Type != model.TensorInt8 && t.Type != model.TensorUint8 && t.Type != model.TensorInt32 && t.Type != model.TensorInt64 && t.Type != 13 {
				return nil, fmt.Errorf("subgraph %d tensor %d %q has unsupported/float type %d", gi, ti, t.Name, t.Type)
			}
			for _, d := range t.Shape {
				if d < 1 {
					return nil, fmt.Errorf("subgraph %d tensor %q has nonstatic shape %v", gi, t.Name, t.Shape)
				}
			}
			if t.Type == model.TensorInt8 || t.Type == model.TensorUint8 {
				if len(t.Quant.Scale) == 0 || len(t.Quant.ZeroPoint) == 0 {
					return nil, fmt.Errorf("unquantized 8-bit tensor %s", t.Name)
				}
				for _, s := range t.Quant.Scale {
					if s <= 0 || math.IsNaN(float64(s)) || math.IsInf(float64(s), 0) {
						return nil, fmt.Errorf("invalid quant scale for %s", t.Name)
					}
				}
			}
		}
		for oi, op := range g.Operators {
			if !supported[op.OpCode] {
				return nil, fmt.Errorf("subgraph %d op %d: %s (%d) is absent from pinned Go dispatch", gi, oi, model.OpName(op.OpCode), op.OpCode)
			}
			seen[op.OpCode] = true
			for _, index := range op.Inputs {
				if index < 0 || index >= len(g.Tensors) {
					return nil, fmt.Errorf("subgraph %d op %d %s input tensor %d is absent/out of bounds; pinned kernels require an explicit bias tensor (zero dense bias can be optimized away)", gi, oi, model.OpName(op.OpCode), index)
				}
			}
			if a, ok := op.Options["fused_activation"].(int); ok && a != 0 && (a != 1 || op.OpCode == model.OpConcatenation) {
				return nil, fmt.Errorf("unsupported fused activation %d on %s (RELU6 upper clamp is absent)", a, model.OpName(op.OpCode))
			}
			if op.OpCode == model.OpStridedSlice {
				for _, k := range []string{"ellipsis_mask", "new_axis_mask", "shrink_axis_mask"} {
					if v, ok := op.Options[k].(int); ok && v != 0 {
						return nil, fmt.Errorf("STRIDED_SLICE %s=%d not implemented by pinned runtime", k, v)
					}
				}
			}
			if op.OpCode == model.OpConv2D || op.OpCode == model.OpDepthwiseConv2D || op.OpCode == model.OpFullyConnected {
				if len(op.Inputs) < 2 {
					return nil, errors.New("convolution/dense missing weight tensor")
				}
				w := g.Tensors[op.Inputs[1]]
				if w.Type != model.TensorInt8 {
					return nil, fmt.Errorf("%s weights must be INT8", model.OpName(op.OpCode))
				}
				for _, z := range w.Quant.ZeroPoint {
					if z != 0 {
						return nil, fmt.Errorf("%s weight zero-point %d unsupported; kernel assumes 0", model.OpName(op.OpCode), z)
					}
				}
			}
		}
	}
	for _, op := range []int{129, 142, 143, 144} {
		if !seen[op] {
			return nil, fmt.Errorf("missing streaming-state op %s; nonstreaming export is not accepted", model.OpName(op))
		}
	}
	var names []string
	for op := range seen {
		names = append(names, model.OpName(op))
	}
	sort.Strings(names)
	return names, nil
}
func checkQuant(t model.Tensor, scale float64, zp int64, relativeTolerance float64) error {
	if len(t.Quant.Scale) != 1 || len(t.Quant.ZeroPoint) != 1 || t.Quant.ZeroPoint[0] != zp || math.Abs(float64(t.Quant.Scale[0])-scale) > relativeTolerance*scale {
		return fmt.Errorf("need scalar quantization scale≈%.12g zero_point=%d, got %+v", scale, zp, t.Quant)
	}
	return nil
}
func invoke(i *interpreter.Interpreter, features []int8) (uint8, error) {
	if err := i.SetInput(features); err != nil {
		return 0, err
	}
	if err := i.Invoke(); err != nil {
		return 0, err
	}
	out := i.OutputUint8()
	if len(out) != 1 {
		return 0, fmt.Errorf("output has %d bytes, want 1", len(out))
	}
	return out[0], nil
}
func runFrames(i *interpreter.Interpreter, frames [][]int8, stride, window int) ([]score, error) {
	var results []score
	ring := make([]uint8, window)
	features := make([]int8, stride*40)
	for k := 0; k+stride <= len(frames); k += stride {
		for j := 0; j < stride; j++ {
			copy(features[j*40:], frames[k+j])
		}
		p, err := invoke(i, features)
		if err != nil {
			return nil, fmt.Errorf("audio/features invocation %d: %w", len(results)+1, err)
		}
		n := len(results)
		ring[n%window] = p
		sum := 0
		for _, x := range ring {
			sum += int(x)
		}
		denom := n + 1
		if denom > window {
			denom = window
		}
		results = append(results, score{n + 1, p, float64(sum) / float64(denom) / 255})
	}
	return results, nil
}
func privateWrite(path string, data []byte) error {
	f, err := os.OpenFile(path, os.O_CREATE|os.O_WRONLY|os.O_EXCL, 0600)
	if err != nil {
		return err
	}
	defer f.Close()
	if err = f.Chmod(0600); err != nil {
		return err
	}
	_, err = f.Write(data)
	return err
}
func writeScores(path string, scores []score, stride, step int) error {
	f, err := os.OpenFile(path, os.O_CREATE|os.O_WRONLY|os.O_EXCL, 0600)
	if err != nil {
		return err
	}
	defer f.Close()
	if err = f.Chmod(0600); err != nil {
		return err
	}
	w := csv.NewWriter(f)
	if err = w.Write([]string{"invocation", "frame_end_ms", "raw_uint8", "sliding_average"}); err != nil {
		return err
	}
	for _, s := range scores {
		if err = w.Write([]string{strconv.Itoa(s.Invocation), strconv.Itoa(30 + (s.Invocation*stride-1)*step), strconv.Itoa(int(s.Raw)), strconv.FormatFloat(s.Average, 'g', 17, 64)}); err != nil {
			return err
		}
	}
	w.Flush()
	return w.Error()
}
func readWAV(path string) ([]int16, error) {
	b, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	if len(b) < 12 || string(b[:4]) != "RIFF" || string(b[8:12]) != "WAVE" {
		return nil, errors.New("need RIFF WAVE")
	}
	validFmt := false
	var pcm []int16
	for off := 12; off+8 <= len(b); {
		kind := string(b[off : off+4])
		size := int(binary.LittleEndian.Uint32(b[off+4 : off+8]))
		start := off + 8
		end := start + size
		if end > len(b) || end < start {
			return nil, errors.New("truncated WAV chunk")
		}
		chunk := b[start:end]
		if kind == "fmt " {
			if size < 16 {
				return nil, errors.New("short WAV fmt")
			}
			validFmt = binary.LittleEndian.Uint16(chunk) == 1 && binary.LittleEndian.Uint16(chunk[2:]) == 1 && binary.LittleEndian.Uint32(chunk[4:]) == 16000 && binary.LittleEndian.Uint16(chunk[12:]) == 2 && binary.LittleEndian.Uint16(chunk[14:]) == 16
		}
		if kind == "data" {
			if size%2 != 0 {
				return nil, errors.New("unaligned PCM16 WAV")
			}
			for j := 0; j < size; j += 2 {
				pcm = append(pcm, int16(binary.LittleEndian.Uint16(chunk[j:])))
			}
		}
		off = end + (size % 2)
	}
	if !validFmt || len(pcm) == 0 {
		return nil, errors.New("WAV must be PCM16 mono 16000Hz with data")
	}
	return pcm, nil
}
