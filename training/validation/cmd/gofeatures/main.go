// Convert stdin PCM16 little-endian mono 16kHz to row-major float32LE features.
// Each output frame has 40 channels; one frame per 10ms after a 30ms window.
// Values dequantize the EXACT EchoLocal 0.0.8 int8 frontend output using 26/255.
package main

import (
	"encoding/binary"
	"fmt"
	"io"
	"math"
	"os"

	"github.com/zserge/microwakeword/audiofrontend"
)

func main() {
	if err := run(); err != nil {
		fmt.Fprintln(os.Stderr, "gofeatures:", err)
		os.Exit(1)
	}
}
func run() error {
	if len(os.Args) != 1 {
		return fmt.Errorf("takes no arguments; stdin=16kHz mono int16LE PCM, stdout=40-column float32LE frames")
	}
	const maxBytes = 32 * 1024 * 1024
	data, err := io.ReadAll(io.LimitReader(os.Stdin, maxBytes+1))
	if err != nil {
		return err
	}
	if len(data) > maxBytes {
		return fmt.Errorf("PCM input exceeds 32MiB per clip")
	}
	if len(data)%2 != 0 {
		return fmt.Errorf("odd PCM byte count %d", len(data))
	}
	if len(data) < 960 {
		return fmt.Errorf("PCM needs at least 480 samples (30ms)")
	}
	pcm := make([]int16, len(data)/2)
	for i := range pcm {
		pcm[i] = int16(binary.LittleEndian.Uint16(data[i*2:]))
	}
	frames := audiofrontend.New(audiofrontend.DefaultConfig(10)).ProcessAllInt8(pcm)
	out := make([]byte, len(frames)*40*4)
	for i, f := range frames {
		for j, q := range f {
			value := float32(int(q)+128) * (float32(26) / 255)
			binary.LittleEndian.PutUint32(out[(i*40+j)*4:], math.Float32bits(value))
		}
	}
	_, err = os.Stdout.Write(out)
	return err
}
