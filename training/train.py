"""Bounded training with validation-only checkpoint selection and explicit inputs."""
import argparse
import json
from pathlib import Path
import time
from common import DEFAULT_CONFIG, candidate_dir, read_config, sha256, work_dir, write_json


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
    args=parser.parse_args()
    work,cfg=work_dir(args.work_dir),read_config(args.config)
    destination=candidate_dir(work,args.candidate)
    if destination.exists(): raise ValueError("Candidate exists; choose a new name, including after an interrupted run")
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
    write_json(destination/"recipe.json",recipe,exclusive=True)
    model=build(cfg)
    model.compile(optimizer=tf.keras.optimizers.Adam(budget["learning_rate"]),loss="binary_crossentropy",jit_compile=False)
    npos=batch["positive"];nneg=sum(batch.values())-npos
    y=np.concatenate([np.ones(npos),np.zeros(nneg)]).astype(np.float32)[:,None]
    weights=np.concatenate([np.ones(npos),np.full(nneg,budget["negative_weight"])]).astype(np.float32)
    best,stale,start,history=float("inf"),0,time.monotonic(),[]
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
        if validation["weighted_loss"]<best:
            best,stale=validation["weighted_loss"],0;model.save_weights(destination/"best.weights.h5")
        else:
            stale+=1
            if stale==2: model.optimizer.learning_rate.assign(float(model.optimizer.learning_rate.numpy())*.5)
            if stale>=budget["early_stopping_patience"]: break
    model.load_weights(destination/"best.weights.h5")
    write_json(destination/"evaluation-nonstreaming.json",{"validation":evaluate(model,val,with_libri),"updates":step,"test_data_read":False})
    write_json(destination/"training-complete.json",{"weights_sha256":sha256(destination/"best.weights.h5"),"updates":step,"best_validation_loss":best},exclusive=True)
    print("Training complete; run export, exact-runtime calibration, frozen test, and human acceptance separately.")


if __name__=="__main__": main()
