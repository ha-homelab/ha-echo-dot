"""Bounded training with validation-only checkpoint selection and explicit inputs."""
import argparse
import json
import math
from pathlib import Path
import re
import time
from common import DEFAULT_CONFIG, candidate_dir, read_config, require_profile_identity, sha256, work_dir, write_json


def initial_weights_provenance(path, expected_sha256, cfg):
    """Verify an explicit checkpoint and its architecture without importing ML libraries.

    Current recipes wrap configuration in ``config``; the historical pilot uses
    ``frames`` and ``flags``. Require one of those recipes beside the checkpoint:
    matching HDF5 tensor shapes alone cannot prove matching architecture options.
    """
    if path is None and expected_sha256 is None:
        return None
    if path is None or expected_sha256 is None:
        raise ValueError("--initial-weights and --initial-weights-sha256 must be supplied together")
    if not re.fullmatch(r"[0-9a-fA-F]{64}", expected_sha256):
        raise ValueError("--initial-weights-sha256 must be a full SHA-256 hexadecimal digest")
    source = Path(path).expanduser().resolve(strict=True)
    if not source.is_file() or not source.name.endswith(".weights.h5"):
        raise ValueError("Initial weights must be a Keras .weights.h5 checkpoint")
    expected_sha256 = expected_sha256.lower()
    if sha256(source) != expected_sha256:
        raise ValueError("Initial checkpoint SHA-256 mismatch")
    recipe_path = source.with_name("recipe.json")
    recipe_digest = sha256(recipe_path)
    recipe = json.loads(recipe_path.read_text())
    if "config" in recipe:
        saved = recipe["config"]
        frames, architecture = saved["frames"], saved["architecture"]
        if saved["feature_step_ms"] != cfg["feature_step_ms"]:
            raise ValueError("Initial checkpoint recipe has a different feature cadence")
        recipe_format = "config"
    elif "frames" in recipe and "flags" in recipe:
        frames, architecture = recipe["frames"], recipe["flags"]
        recipe_format = "legacy_frames_flags"
    else:
        raise ValueError("Initial checkpoint needs an adjacent recipe.json with a known architecture format")
    if frames != cfg["frames"] or architecture != cfg["architecture"]:
        raise ValueError("Initial checkpoint recipe does not match the configured architecture")
    if sha256(recipe_path) != recipe_digest:
        raise ValueError("Initial checkpoint recipe changed while being read")
    return {"path": str(source), "sha256": expected_sha256,
            "recipe_path": str(recipe_path), "recipe_sha256": recipe_digest,
            "recipe_format": recipe_format, "frames": frames, "architecture": architecture,
            "feature_step_ms_recorded": recipe_format == "config",
            "loading": "strict weights only, before optimizer construction",
            "optimizer": "fresh Adam; source optimizer state is not restored"}


def compile_for_training(model, tf, budget, initial=None):
    """Strictly load a verified checkpoint before creating a new optimizer."""
    if initial is not None:
        def verify_sources():
            if sha256(initial["path"]) != initial["sha256"]:
                raise ValueError("Initial checkpoint changed before/during loading")
            if sha256(initial["recipe_path"]) != initial["recipe_sha256"]:
                raise ValueError("Initial checkpoint recipe changed before/during loading")
        verify_sources()
        # The model is built from the checked current architecture and is not yet
        # compiled. Never use by-name loading, skip_mismatch, or load_model here.
        model.load_weights(initial["path"], skip_mismatch=False)
        verify_sources()
    model.compile(optimizer=tf.keras.optimizers.Adam(budget["learning_rate"]),
                  loss="binary_crossentropy", jit_compile=False)


def checkpoint_if_better(model, destination, validation, best):
    """Keep the existing checkpoint on ties, regressions, or invalid losses."""
    loss = validation["weighted_loss"]
    if not math.isfinite(loss):
        raise ValueError("Validation loss is not finite; refusing checkpoint selection")
    if loss < best:
        model.save_weights(destination / "best.weights.h5")
        return loss, True
    return best, False


def load(work, name, empty_ok=False):
    import numpy as np
    array = np.load(work/"features"/(name+".npy"), mmap_mode="r", allow_pickle=False)
    if array.ndim != 3 or tuple(array.shape[1:]) != (250,40) or (not len(array) and not empty_ok):
        raise ValueError(f"Invalid feature shape/count: {name}")
    if len(array) and (not np.isfinite(array).all() or array.min() < 0 or array.max() > 26):
        raise ValueError(f"Features must be finite and in model units 0..26: {name}")
    return array


def predict(model, array):
    import numpy as np
    return np.concatenate([model(np.asarray(array[i:i+128],np.float32),training=False).numpy()[:,0]
                           for i in range(0,len(array),128)])


def evaluate(model, arrays, with_libri):
    import numpy as np
    result, scores = {}, {}
    for name, array in arrays.items():
        if not len(array):
            result[name] = {"n": 0, "status": "not_evaluated"}; continue
        values = predict(model,array)
        scores[name] = np.clip(values,1e-6,1-1e-6)
        result[name] = {"n":len(values),"mean":float(values.mean()),"max":float(values.max()),
                        "above_cutoff":{str(t):int(np.sum(values>=t)) for t in [.5,.65,.75,.85,.9,.95]}}
    p,h,b = scores["tts_val_1"],scores["tts_val_0"],scores["background_val"]
    loss = -.5*np.mean(np.log(p))-.5*np.mean(np.log(1-h))
    if with_libri:
        loss -= .15*np.mean(np.log(1-b))+.35*np.mean(np.log(1-scores["librispeech_val"]))
    else: loss -= .5*np.mean(np.log(1-b))
    # Personalization validation must come from separately imported sessions.
    for name in ("real_val_1","real_val_0"):
        if name in scores:
            loss -= .5*np.mean(np.log(scores[name] if name.endswith("1") else 1-scores[name]))
    result["weighted_loss"] = float(loss)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work-dir",required=True)
    parser.add_argument("--candidate",required=True)
    parser.add_argument("--config",default=str(DEFAULT_CONFIG))
    parser.add_argument("--without-librispeech",action="store_true",help="Reproduce the earlier candidate-1 ablation")
    parser.add_argument("--with-recordings",action="store_true",help="Blend imported train sessions; never read the test partition")
    parser.add_argument("--initial-weights",type=Path,
                        help="Optional .weights.h5 with adjacent compatible recipe.json; loads weights only")
    parser.add_argument("--initial-weights-sha256",
                        help="Required with --initial-weights: the independently recorded full checkpoint SHA-256")
    args=parser.parse_args()
    work,cfg=work_dir(args.work_dir),read_config(args.config)
    destination=candidate_dir(work,args.candidate)
    if destination.exists(): raise ValueError("Candidate exists; choose a new name, including after an interrupted run")
    require_profile_identity(work,cfg)
    initial=initial_weights_provenance(args.initial_weights,args.initial_weights_sha256,cfg)
    from model import initialize,build
    tf=initialize(work,cfg)
    import numpy as np
    rng=np.random.default_rng(cfg["seed"])
    train={name:load(work,name) for name in ("tts_train_1","tts_train_0","background_train")}
    val={name:load(work,name) for name in ("tts_val_1","tts_val_0","background_val")}
    with_libri=not args.without_librispeech
    if with_libri:
        train["librispeech_train"]=load(work,"librispeech_train")
        val["librispeech_val"]=load(work,"librispeech_val")
    if args.with_recordings:
        for label in (0,1):
            train[f"real_train_{label}"]=load(work,f"real_train_{label}",empty_ok=True)
            val[f"real_val_{label}"]=load(work,f"real_val_{label}",empty_ok=True)
        if not len(train["real_train_1"]): raise ValueError("Personalization needs positive train-session recordings")
    metadata={name:{"shape":list(array.shape),"sha256":sha256(work/"features"/(name+".npy"))}
              for name,array in {**train,**val}.items()}
    destination.mkdir(parents=True,exist_ok=False)
    budget=cfg["training"]
    batch=dict(budget["batch"])
    if not with_libri: batch["background"]+=batch.pop("librispeech")
    recipe={"config":cfg,"input_features":metadata,"with_recordings":args.with_recordings,
            "batch":batch,"test_data_read":False,"selection":"Lowest weighted validation loss",
            "script_sha256":sha256(__file__),"claim":"Not human acoustic acceptance"}
    if initial is not None:
        recipe["initial_weights"]=initial
        recipe["selection"]="Lowest weighted validation loss, including the initial checkpoint at step 0"
    write_json(destination/"recipe.json",recipe,exclusive=True)
    model=build(cfg)
    compile_for_training(model,tf,budget,initial)
    npos=batch["positive"];nneg=sum(batch.values())-npos
    y=np.concatenate([np.ones(npos),np.zeros(nneg)]).astype(np.float32)[:,None]
    weights=np.concatenate([np.ones(npos),np.full(nneg,budget["negative_weight"])]).astype(np.float32)
    best,stale,start,history=float("inf"),0,time.monotonic(),[]
    best_step=None
    if initial is not None:
        baseline=evaluate(model,val,with_libri)
        best,_=checkpoint_if_better(model,destination,baseline,best)
        best_step=0
        entry={"step":0,"seconds":time.monotonic()-start,"train_loss":None,
               "validation":baseline,"kind":"initial_weights_baseline"}
        history.append(entry);write_json(destination/"history.json",history)
        write_json(destination/"baseline-validation.json",{
            "validation":baseline,"initial_weights_sha256":initial["sha256"],
            "weights_sha256":sha256(destination/"best.weights.h5"),
            "optimizer_updates":0,"test_data_read":False},exclusive=True)
        print(json.dumps(entry),flush=True)
    def sample(name,count):
        array=train[name]
        return array[rng.integers(0,len(array),count)]
    for step in range(1,budget["max_updates"]+1):
        real_pos=min(8,npos//2) if args.with_recordings and len(train["real_train_1"]) else 0
        hard_count=batch["hard_negative"]
        real_neg=min(8,hard_count//2) if args.with_recordings and len(train["real_train_0"]) else 0
        parts=[sample("tts_train_1",npos-real_pos)]
        if real_pos: parts.append(sample("real_train_1",real_pos))
        parts.append(sample("tts_train_0",hard_count-real_neg))
        if real_neg: parts.append(sample("real_train_0",real_neg))
        parts.append(sample("background_train",batch["background"]))
        if with_libri: parts.append(sample("librispeech_train",batch["librispeech"]))
        x=np.concatenate(parts).astype(np.float32)
        for i in range(len(x)):
            if rng.random()<.35:
                width=int(rng.integers(1,4));at=int(rng.integers(0,40-width+1));x[i,:,at:at+width]=0
            if rng.random()<.25:
                width=int(rng.integers(1,13));at=int(rng.integers(0,250-width+1));x[i,at:at+width]=0
        metrics=model.train_on_batch(x,y,sample_weight=weights,return_dict=True)
        if step%budget["validation_interval"] and step!=budget["max_updates"]: continue
        validation=evaluate(model,val,with_libri)
        entry={"step":step,"seconds":time.monotonic()-start,"train_loss":float(metrics["loss"]),"validation":validation}
        history.append(entry);write_json(destination/"history.json",history)
        print(json.dumps(entry),flush=True);model.reset_metrics()
        best,improved=checkpoint_if_better(model,destination,validation,best)
        if improved:
            stale=0;best_step=step
        else:
            stale+=1
            if stale==2: model.optimizer.learning_rate.assign(float(model.optimizer.learning_rate.numpy())*.5)
            if stale>=budget["early_stopping_patience"]: break
    model.load_weights(destination/"best.weights.h5")
    write_json(destination/"evaluation-nonstreaming.json",{"validation":evaluate(model,val,with_libri),"updates":step,"test_data_read":False})
    completion={"weights_sha256":sha256(destination/"best.weights.h5"),"updates":step,"best_validation_loss":best}
    if initial is not None:
        completion.update({"initial_weights_sha256":initial["sha256"],
                           "baseline_validation_loss":baseline["weighted_loss"],
                           "best_validation_step":best_step,"selection_includes_initial_weights":True,
                           "optimizer_initialized_fresh":True})
    write_json(destination/"training-complete.json",completion,exclusive=True)
    print("Training complete; run export, exact-runtime calibration, frozen test, and human acceptance separately.")


if __name__=="__main__": main()
