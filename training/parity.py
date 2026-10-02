"""Compare exact-Go and TensorFlow output traces without hiding numeric failures."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import wave
from common import SOURCE, sha256, work_dir, write_json


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work-dir",required=True)
    parser.add_argument("--model",required=True)
    parser.add_argument("--wav",required=True)
    parser.add_argument("--name",required=True)
    parser.add_argument("--cutoff",type=float,default=.9)
    args=parser.parse_args()
    if not args.name.replace("-","").replace("_","").isalnum(): parser.error("Use a safe trace name")
    if not 0<=args.cutoff<=1: parser.error("cutoff must be 0..1")
    work=work_dir(args.work_dir);out=work/"evaluation/parity"/args.name
    out.mkdir(parents=True,exist_ok=False)
    source=Path(args.wav).resolve();model=Path(args.model).resolve()
    with wave.open(str(source),"rb") as audio:
        if (audio.getnchannels(),audio.getsampwidth(),audio.getframerate())!=(1,2,16000):
            raise ValueError("Trace source must be PCM16 mono 16kHz WAV")
        pcm=audio.readframes(audio.getnframes())
    padded=out/"padded.wav"
    with wave.open(str(padded),"wb") as audio:
        audio.setparams((1,2,16000,0,"NONE","not compressed"))
        audio.writeframes(b"\0"*(3*32000)+pcm+b"\0"*32000)
    command=[str(work/"bin/validate"),"-model",str(model),"-wav",str(padded),
             "-features-out",str(out/"features.int8"),"-scores-out",str(out/"go.csv"),"-threshold",str(args.cutoff)]
    go=subprocess.run(command,capture_output=True,text=True)
    (out/"go.json").write_text(go.stdout);(out/"go.stderr.log").write_text(go.stderr)
    if go.returncode: raise RuntimeError("Go execution failed; inspect the trace directory")
    compare=subprocess.run([sys.executable,str(SOURCE/"validation/compare_tflite.py"),"--model",str(model),
        "--features",str(out/"features.int8"),"--go-scores",str(out/"go.csv"),
        "--scores-out",str(out/"tensorflow.csv"),"--decision-threshold",str(args.cutoff)],capture_output=True,text=True)
    (out/"parity.json").write_text(compare.stdout);(out/"tensorflow.stderr.log").write_text(compare.stderr)
    write_json(out/"inputs.json",{"model_sha256":sha256(model),"source_sha256":sha256(source),
        "padded_sha256":sha256(padded),"leading_zero_seconds":3,"trailing_zero_seconds":1,
        "comparison_exit_code":compare.returncode,"cutoff":args.cutoff})
    print(out/"parity.json")
    if compare.returncode not in (0,2): raise RuntimeError("Comparison failed before a valid result was produced")
    return compare.returncode  # 2 means a recorded strict parity failure, never success.


if __name__=="__main__": sys.exit(main())
