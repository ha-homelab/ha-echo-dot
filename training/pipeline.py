#!/usr/bin/env python3
"""Run one explicit, journaled stage of the EchoLocal wake-word training workflow."""
import argparse
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import platform
import shlex
import shutil
import subprocess
import sys
from common import CORE_REVISION, DEFAULT_CONFIG, SOURCE, read_config, require_profile_identity, sha256, work_dir, write_json

STAGES=("doctor","setup","build","smoke","benchmark","voices","synth-smoke","synth-full",
        "verify-data","background","librispeech","features","import-recording","features-real",
        "train","export","prepare-tts","prepare-speech","parity","calibrate","freeze","test","package","stage-ha")


def execute(command,dry_run=False,cwd=None):
    print(shlex.join(map(str,command)),flush=True)
    if dry_run:return 0
    return subprocess.run(list(map(str,command)),cwd=cwd).returncode


def setup(work,args,dry_run):
    parser=argparse.ArgumentParser(prog="pipeline.py setup")
    parser.add_argument("--python",default="3.11")
    parser.add_argument("--reference-lock",action="store_true",help="Use the complete tested macOS ARM64 environment")
    opts=parser.parse_args(args)
    if opts.reference_lock and (platform.system(),platform.machine())!=("Darwin","arm64"):
        raise ValueError("The reference lock is specific to macOS ARM64; use direct requirements on other hosts")
    lock=SOURCE/("requirements-macos-arm64.lock.txt" if opts.reference_lock else "requirements.txt")
    if shutil.which("uv") is None:raise ValueError("Install uv before setup")
    if not dry_run:
        work.mkdir(parents=True,exist_ok=True)
        if not (work/".venv").exists():
            subprocess.run(["uv","venv","--python",opts.python,str(work/".venv")],check=True)
    else:execute(["uv","venv","--python",opts.python,work/".venv"],True)
    if execute(["uv","pip","install","--python",work/".venv/bin/python","-r",lock],dry_run):return 1
    vendor=work/"vendor/micro-wake-word"
    if not vendor.exists():
        for command in (["git","init",str(vendor)],
                        ["git","-C",str(vendor),"remote","add","origin","https://github.com/kahrendt/microWakeWord.git"],
                        ["git","-C",str(vendor),"fetch","--depth","1","origin",CORE_REVISION],
                        ["git","-C",str(vendor),"checkout","--detach",CORE_REVISION]):
            if execute(command,dry_run):return 1
    elif not dry_run:
        head=subprocess.check_output(["git","-C",str(vendor),"rev-parse","HEAD"],text=True).strip()
        dirty=subprocess.check_output(["git","-C",str(vendor),"status","--porcelain"],text=True).strip()
        if head!=CORE_REVISION or dirty:raise ValueError("Existing builder is modified or at another revision; use a new work directory")
    if not dry_run:
        freeze=subprocess.check_output(["uv","pip","freeze","--python",str(work/".venv/bin/python")],text=True)
        (work/"environment-resolved.txt").write_text(freeze)
        write_json(work/"environment.json",{"python":opts.python,"platform":platform.platform(),
            "requirements_sha256":sha256(lock),"core_revision":CORE_REVISION,"reference_lock":opts.reference_lock})
    return 0


def build(work,dry_run):
    if shutil.which("go") is None:raise ValueError("Install Go 1.26 or newer before build")
    paths=sorted((SOURCE/"validation").rglob("*.go"))+[SOURCE/"validation/go.mod",SOURCE/"validation/go.sum"]
    identity={str(p.relative_to(SOURCE/"validation")):sha256(p) for p in paths}
    receipt=work/"bin/build.json"
    if receipt.exists():
        previous=json.loads(receipt.read_text())
        if previous["sources"]!=identity:raise ValueError("Validator source changed; use a new work directory to preserve frozen binary hashes")
        if all((work/"bin"/name).is_file() and sha256(work/"bin"/name)==digest for name,digest in previous["binaries"].items()):
            print("Existing pinned binaries verified");return 0
        raise ValueError("Existing compiled binary changed; use a new work directory")
    if any((work/"bin"/name).exists() for name in ("validate", "gofeatures")):
        raise ValueError("Unreceipted binaries already exist; preserve them and use a new work directory")
    if not dry_run:(work/"bin").mkdir(parents=True,exist_ok=True)
    for name,package in (("validate","."),("gofeatures","./cmd/gofeatures")):
        code=execute(["go","build","-trimpath","-o",work/"bin"/name,package],dry_run,cwd=SOURCE/"validation")
        if code:return code
    if not dry_run:write_json(receipt,{"sources":identity,"binaries":{n:sha256(work/"bin"/n) for n in ("validate","gofeatures")}},exclusive=True)
    return 0


def delegated(stage,work,config,extra):
    py=work/".venv/bin/python"
    wd=["--work-dir",str(work)]
    cfg=["--config",str(config)]
    profile=["--profile",read_config(config).get("synthesis_profile","pm-v1")]
    routes={
        "smoke":["model.py","smoke",*wd,*cfg],"benchmark":["model.py","benchmark",*wd,*cfg],
        "voices":["data/generate.py",*wd,"--stage","download",*profile],
        "synth-smoke":["data/generate.py",*wd,"--stage","smoke",*profile],
        "synth-full":["data/generate.py",*wd,"--stage","full",*profile],
        "verify-data":["data/verify.py",*wd,*profile],
        "background":["data/background.py","all",*wd],
        "librispeech":["data/librispeech.py","all",*wd],
        "features":["features.py",*wd,*cfg],"features-real":["features.py",*wd,*cfg,"--kind","real"],
        "train":["train.py",*wd,*cfg],"export":["model.py","export",*wd,*cfg],
        "import-recording":["recordings.py","import",*wd],
        "prepare-tts":["evaluate.py","prepare-tts",*wd],
        "prepare-speech":["validation/prepare_librispeech_eval.py","--librispeech",str(work/"librispeech")],
        "parity":["parity.py",*wd],
        "calibrate":["evaluate.py","calibrate",*wd],"freeze":["evaluate.py","freeze",*wd],
        "test":["evaluate.py","test",*wd],"package":["delivery.py","package",*wd],
        "stage-ha":["delivery.py","stage"],
    }
    script,*parameters=routes[stage]
    return [str(py),str(SOURCE/script),*parameters,*extra]


def main():
    parser=argparse.ArgumentParser(description=__doc__,epilog="Global options precede the stage. Remaining arguments go to that stage's --help.")
    parser.add_argument("--work-dir",default=str(SOURCE.parent/"private/wakeword-runs/myshka-v1"))
    parser.add_argument("--config")
    parser.add_argument("--dry-run",action="store_true")
    parser.add_argument("stage",choices=STAGES)
    parser.add_argument("stage_args",nargs=argparse.REMAINDER)
    args=parser.parse_args()
    if args.stage in ("doctor", "build"):
        stage_parser=argparse.ArgumentParser(prog=f"pipeline.py {args.stage}",
            description="Read-only environment inspection" if args.stage=="doctor" else "Build immutable pinned Go validation binaries")
        stage_parser.parse_args(args.stage_args)
    work=work_dir(args.work_dir)
    config=Path(args.config).resolve() if args.config else (work/"recipe.json" if (work/"recipe.json").exists() else DEFAULT_CONFIG)
    cfg=read_config(config)
    if args.stage in ("setup", "smoke", "benchmark", "voices", "synth-smoke", "synth-full",
                      "verify-data", "features", "features-real", "train", "export") and "--help" not in args.stage_args:
        require_profile_identity(work,cfg)
    saved_recipe=work/"recipe.json"
    if args.stage=="setup" and saved_recipe.exists() and json.loads(saved_recipe.read_text())!=cfg:
        raise ValueError("Work directory already has a different recipe; use a new work directory")
    if args.stage=="doctor":
        print(json.dumps({"work_dir":str(work),"platform":platform.platform(),"tools":{x:shutil.which(x) for x in ("uv","git","go","ffmpeg")},
            "python_environment_exists":(work/".venv/bin/python").exists(),"free_disk_gib":round(shutil.disk_usage(work if work.exists() else SOURCE).free/2**30,1),
            "live_device_access":False},indent=2));return 0
    if args.stage=="setup":code=setup(work,args.stage_args,args.dry_run)
    elif args.stage=="build":code=build(work,args.dry_run)
    else:
        command=delegated(args.stage,work,config,args.stage_args)
        if not args.dry_run and not Path(command[0]).exists():
            # Help for all stages is available before installing the ML environment.
            if "--help" in args.stage_args:command[0]=sys.executable
            else:raise ValueError("Run setup first, or invoke an individual script with an existing compatible Python environment")
        code=execute(command,args.dry_run)
    if args.dry_run or "--help" in args.stage_args:return code
    work.mkdir(parents=True,exist_ok=True)
    if args.stage=="setup" and code==0:
        target=work/"recipe.json"
        if target.exists() and json.loads(target.read_text())!=cfg:raise ValueError("Work directory already has a different recipe")
        if not target.exists():write_json(target,cfg,exclusive=True)
    with (work/"stages.jsonl").open("a") as log:
        log.write(json.dumps({"at":datetime.now(timezone.utc).isoformat(),"stage":args.stage,"arguments":args.stage_args,
            "config_sha256":sha256(config),"exit_code":code})+"\n")
    return code


if __name__=="__main__":
    try:sys.exit(main())
    except (ValueError,OSError,subprocess.SubprocessError) as exc:
        print(f"Stage failed: {exc}",file=sys.stderr);sys.exit(1)
