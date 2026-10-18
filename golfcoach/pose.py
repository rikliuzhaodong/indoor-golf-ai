from pathlib import Path
import urllib.request
import cv2
import numpy as np
from .io import frames

MODEL_URL = 'https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_full/float16/1/pose_landmarker_full.task'
EDGES = [(0,11),(0,12),(11,12),(11,13),(13,15),(12,14),(14,16),(11,23),(12,24),(23,24),(23,25),(25,27),(24,26),(26,28),(27,29),(29,31),(28,30),(30,32)]


def extract(video, cfg, model_dir):
    import mediapipe as mp
    model = Path(model_dir)/'pose_landmarker_full.task'
    if not model.exists():
        model.parent.mkdir(parents=True, exist_ok=True)
        tmp = model.with_suffix('.download')
        urllib.request.urlretrieve(MODEL_URL, tmp)
        tmp.replace(model)
    opts = mp.tasks.vision.PoseLandmarkerOptions(
        base_options=mp.tasks.BaseOptions(model_asset_path=str(model), delegate=mp.tasks.BaseOptions.Delegate.CPU),
        running_mode=mp.tasks.vision.RunningMode.VIDEO, num_poses=cfg['max_people'],
        min_pose_detection_confidence=cfg['confidence'], min_pose_presence_confidence=cfg['confidence'])
    tracks, rows = [], []
    with mp.tasks.vision.PoseLandmarker.create_from_options(opts) as detector:
        for i,t,im in frames(video):
            h,w = im.shape[:2]
            row = {'frame':i,'timestamp':t,'landmarks':None,'confidence':0.,'method':'not_sampled'}
            if i % cfg['stride'] == 0:
                result = detector.detect_for_video(mp.Image(image_format=mp.ImageFormat.SRGB, data=cv2.cvtColor(im,cv2.COLOR_BGR2RGB)), round(t*1000))
                used = set()
                for person in result.pose_landmarks:
                    p = np.array([[p.x*w,p.y*h,p.visibility] for p in person])
                    center = p[[23,24],:2].mean(axis=0)
                    candidates = [(np.linalg.norm(center-tr['center']),n) for n,tr in enumerate(tracks) if n not in used and t-tr['last']<0.6]
                    dist,n = min(candidates,default=(1e10,-1))
                    if dist > w*0.18:
                        n = len(tracks)
                        tracks.append({'center':center,'last':t,'samples':[]})
                    tr = tracks[n]
                    tr['center'],tr['last'] = center,t
                    tr['samples'].append((len(rows),p))
                    used.add(n)
                row['method']='mediapipe_cpu_no_detection'
            rows.append(row)
            if i % 300 == 0:
                print(f'姿态 {t:.1f}s', flush=True)
    if not tracks:
        return rows, {'confidence':0.,'method':'multi_person_motion_selection','reason':'未检测到人体'}
    def score(tr):
        ps = np.array([p for _,p in tr['samples']])
        if len(ps)<4:
            return 0.
        body = np.maximum(np.linalg.norm(ps[:,11,:2]-ps[:,23,:2],axis=1),1)
        wrist = ps[:,[15,16],:2].mean(axis=1)-ps[:,[23,24],:2].mean(axis=1)
        motion = np.percentile(np.linalg.norm(np.diff(wrist,axis=0),axis=1)/body[1:],90)
        size = np.median(body)/h
        centrality = 1-abs(np.median(ps[:,23,0])/w-.5)
        return float(motion*2+size+centrality*.15)*min(len(ps)/20,1)
    ranked = sorted(tracks,key=score,reverse=True)
    selected = ranked[0]
    confidence = .8 if len(ranked)==1 else float(np.clip((score(selected)-score(ranked[1]))/max(score(selected),.001),0,.8))
    smooth = None
    last = -100
    for idx,p in selected['samples']:
        t = rows[idx]['timestamp']
        if smooth is None or t-last>cfg['max_gap_seconds']:
            smooth=p.copy()
        else:
            a=cfg['smoothing_alpha']
            good=(p[:,2]>=cfg['confidence']) & (smooth[:,2]>=cfg['confidence'])
            p[good,:2]=a*p[good,:2]+(1-a)*smooth[good,:2]
            smooth=p.copy()
        rows[idx].update(landmarks=[{'x':float(x),'y':float(y),'confidence':float(c)} for x,y,c in p], confidence=float(np.mean(p[:,2])), method='mediapipe_ema')
        last=t
    # Interpolate only short gaps with valid endpoints; never extrapolate occlusions.
    ids=[i for i,r in enumerate(rows) if r['landmarks']]
    for a,b in zip(ids,ids[1:]):
        if rows[b]['timestamp']-rows[a]['timestamp'] > cfg['max_gap_seconds']:
            continue
        for j in range(a+1,b):
            f=(rows[j]['timestamp']-rows[a]['timestamp'])/(rows[b]['timestamp']-rows[a]['timestamp'])
            rows[j]['landmarks']=[{'x':u['x']*(1-f)+v['x']*f,'y':u['y']*(1-f)+v['y']*f,'confidence':min(u['confidence'],v['confidence'])*.8} for u,v in zip(rows[a]['landmarks'],rows[b]['landmarks'])]
            rows[j].update(confidence=min(rows[a]['confidence'],rows[b]['confidence'])*.8, method='short_gap_interpolation')
    return rows, {'confidence':confidence,'method':'body_relative_wrist_motion_size_center_identity_gating','candidate_tracks':len(tracks),'reason':None if confidence>=.3 else '多人身份选择有歧义，请裁剪到挥杆者后复跑'}


def draw(im,row):
    ps=row['landmarks']
    if not ps:
        return
    for a,b in EDGES:
        if min(ps[a]['confidence'],ps[b]['confidence'])>.5:
            cv2.line(im,(round(ps[a]['x']),round(ps[a]['y'])),(round(ps[b]['x']),round(ps[b]['y'])),(70,220,80),2)
    for p in ps:
        if p['confidence']>.5:
            cv2.circle(im,(round(p['x']),round(p['y'])),4,(0,210,255),-1)
