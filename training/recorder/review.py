#!/usr/bin/env python3
"""Quality summary, explicit transcript review, and guarded per-target import."""
import argparse, json, os, re, sys
from pathlib import Path
from types import SimpleNamespace
from server import atomic, digest, inspect_wav, now
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from recordings import import_recording


def labels(text):
    words=re.findall(r'[а-яё]+',text.casefold())
    return {'myshka':int('мышка' in words), 'privet_myshka':int(any(words[i:i+2]==['привет','мышка'] for i in range(len(words)-1)))}

def load(root):
    campaign=json.loads((root/'campaign.json').read_text())
    reviews=json.loads((root/'reviews.json').read_text()) if (root/'reviews.json').exists() else {}
    return campaign,reviews

def verify(root,take):
    path=root/take['path'];data=path.read_bytes()
    if digest(data)!=take['sha256']:raise ValueError('WAV changed: '+take['id'])
    stats=inspect_wav(data)
    if stats['sample_rate']!=16000:raise ValueError('Expected 16 kHz canonical WAV.')
    return path,stats

def summary(root):
    campaign,reviews=load(root);out={'created_at':now(),'capture_domain':'mac_browser','counts':{},'quality_warnings':[], 'analysis_requests':campaign['analysis_requests']}
    for split in ('train','val','test'):
        takes=[t for t in campaign['takes'] if t['selected'] and t['split']==split]
        out['counts'][split]={'recorded':len(takes),'planned':sum(t['split']==split for t in campaign['plan']),'reviewed':sum(t['id'] in reviews for t in takes)}
        for t in takes:
            _,stats=verify(root,t)
            if stats['flags']:out['quality_warnings'].append({'id':t['id'],'split':split,'flags':stats['flags']})
    out['note']='Level/duration checks do not verify words or model accuracy. Frozen test audio must not be used for model or threshold selection.'
    return out

def review(root,take_id,transcript):
    campaign,reviews=load(root)
    take=next(t for t in campaign['takes'] if t['id']==take_id and t['selected'])
    verify(root,take)
    if not transcript.strip():raise ValueError('An explicit verified transcript is required; discard empty/failed speech attempts.')
    reviews[take_id]={'reviewed_at':now(),'transcript':transcript,'labels':labels(transcript),'sha256':take['sha256'],'method':'operator_verified_transcript'}
    atomic(root/'reviews.json',reviews);return reviews[take_id]

def export(root,destination,include_test=False):
    campaign,reviews=load(root)
    takes=[t for t in campaign['takes'] if t['selected'] and (include_test or t['split']!='test')]
    if not takes:raise ValueError('No selected recordings.')
    # Preflight the whole selection before importing the first clip.
    for t in takes:
        verify(root,t)
        if t['id'] not in reviews or reviews[t['id']]['sha256']!=t['sha256']:
            raise ValueError('Verify the actual transcript first: '+t['id'])
        if reviews[t['id']]['labels']!=labels(reviews[t['id']]['transcript']):raise ValueError('Review labels disagree with transcript.')
    counts={}
    for target in ('myshka','privet_myshka'):
        for t in takes:
            r=reviews[t['id']]
            result=import_recording(SimpleNamespace(work_dir=destination/target,wav=root/t['path'],speaker='owner-01',session=t['session_id'],split=t['split'],label='positive' if r['labels'][target] else 'negative',transcript=r['transcript'],max_seconds=12,split_by='session'))
        counts[target]=result['counts']
    atomic(destination/'recorder-import.json',{'created_at':now(),'source_campaign':str(root),'reviewed_ids':[t['id'] for t in takes],'test_included':include_test,'counts':counts})
    return counts

def main():
    os.umask(0o077);p=argparse.ArgumentParser(description=__doc__);p.add_argument('--data-dir',type=Path,required=True)
    sub=p.add_subparsers(dest='cmd',required=True);sub.add_parser('summary')
    r=sub.add_parser('review');r.add_argument('--take',required=True);r.add_argument('--transcript',required=True)
    e=sub.add_parser('export');e.add_argument('--destination',type=Path,required=True);e.add_argument('--include-frozen-test',action='store_true')
    a=p.parse_args();root=a.data_dir.expanduser().resolve()
    try:
        if a.cmd=='summary':out=summary(root)
        elif a.cmd=='review':out=review(root,a.take,a.transcript)
        else:out=export(root,a.destination.expanduser().resolve(),a.include_frozen_test)
        print(json.dumps(out,ensure_ascii=False,indent=2))
    except (OSError,ValueError,StopIteration) as exc:p.exit(1,str(exc)+'\n')
if __name__=='__main__':main()
