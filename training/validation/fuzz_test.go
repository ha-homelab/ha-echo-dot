package main

import (
	"encoding/binary"
	"encoding/json"
	"testing"

	"github.com/zserge/microwakeword/model"
)

func FuzzModelStructure(f *testing.F) {
	valid := model.Model{Subgraphs: []model.Subgraph{{
		Inputs: []int{0}, Outputs: []int{1},
		Tensors: []model.Tensor{
			{Type: model.TensorInt8, Shape: []int{1, 1, 40}, Quant: model.QuantParams{Scale: []float32{26.0 / 255}, ZeroPoint: []int64{-128}}},
			{Type: model.TensorUint8, Shape: []int{1}, Quant: model.QuantParams{Scale: []float32{1.0 / 256}, ZeroPoint: []int64{0}}},
		},
		Operators: []model.Operator{{OpCode: 129}, {OpCode: 142}, {OpCode: 143}, {OpCode: 144}},
	}}}
	seed, err := json.Marshal(valid)
	if err != nil {
		f.Fatal(err)
	}
	f.Add(seed)
	for _, raw := range []string{`{}`, `{"Subgraphs":[{"Inputs":[0],"Outputs":[0]}]}`, `{"Subgraphs":[{"Inputs":[-1],"Outputs":[99],"Tensors":[{}]}]}`} {
		f.Add([]byte(raw))
	}
	f.Fuzz(func(t *testing.T, raw []byte) {
		if len(raw) > 64*1024 {
			t.Skip()
		}
		var m model.Model
		if json.Unmarshal(raw, &m) != nil {
			return
		}
		_, err := checkModel(&m)
		if err != nil {
			return
		}
		for _, graph := range m.Subgraphs {
			indices := append(append([]int{}, graph.Inputs...), graph.Outputs...)
			for _, operation := range graph.Operators {
				indices = append(indices, operation.Inputs...)
				indices = append(indices, operation.Outputs...)
			}
			for _, index := range indices {
				if index < 0 || index >= len(graph.Tensors) {
					t.Fatal("accepted model references a missing tensor")
				}
			}
		}
	})
}

func fuzzWAV(pcm []byte) []byte {
	pcm = pcm[:len(pcm)/2*2]
	b := make([]byte, 44+len(pcm))
	copy(b, "RIFF")
	binary.LittleEndian.PutUint32(b[4:], uint32(len(b)-8))
	copy(b[8:], "WAVEfmt ")
	binary.LittleEndian.PutUint32(b[16:], 16)
	binary.LittleEndian.PutUint16(b[20:], 1)
	binary.LittleEndian.PutUint16(b[22:], 1)
	binary.LittleEndian.PutUint32(b[24:], 16000)
	binary.LittleEndian.PutUint32(b[28:], 32000)
	binary.LittleEndian.PutUint16(b[32:], 2)
	binary.LittleEndian.PutUint16(b[34:], 16)
	copy(b[36:], "data")
	binary.LittleEndian.PutUint32(b[40:], uint32(len(pcm)))
	copy(b[44:], pcm)
	return b
}

func FuzzWAVInput(f *testing.F) {
	f.Add(fuzzWAV([]byte{0, 0, 255, 127, 0, 128}))
	f.Add([]byte("RIFF\xFF\xFF\xFF\xFFWAVEdata"))
	f.Add([]byte{})
	f.Fuzz(func(t *testing.T, raw []byte) {
		if len(raw) > 64*1024 {
			t.Skip()
		}
		pcm, err := parseWAV(raw)
		if err == nil && (len(pcm) == 0 || len(pcm) > len(raw)/2) {
			t.Fatal("accepted WAV has an impossible sample count")
		}
		// Independent synthetic encoding confirms signed PCM samples survive
		// the real training-input parser exactly, including both extrema.
		if len(raw) >= 2 {
			pcm, err := parseWAV(fuzzWAV(raw))
			if err != nil || len(pcm) != len(raw)/2 {
				t.Fatalf("valid synthetic WAV rejected: %v", err)
			}
			for i, sample := range pcm {
				if sample != int16(binary.LittleEndian.Uint16(raw[i*2:])) {
					t.Fatal("PCM sample changed during parsing")
				}
			}
		}
	})
}
