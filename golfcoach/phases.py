import numpy as np


def estimate(value=None,confidence=0.,method='unavailable',reason=None,unit=None,**extra):
    return dict(value=value,confidence=float(confidence),method=method,reason=reason,unit=unit,**extra)


def segment(rows, manual_impact=None):
    valid=[r for r in rows if r['landmarks'] and min(r['landmarks'][j]['confidence'] for j in [11,12,15,16,23,24])>.5]
    names=['address','takeaway','backswing','top','downswing','impact','follow_through','finish']
    missing={n:estimate(method='wrist_kinematics_2d',reason='有效连续姿态不足') for n in names}
    if len(valid)<12:
        return missing
    ts=np.array([r['timestamp'] for r in valid])
    ps=np.array([[[p['x'],p['y']] for p in r['landmarks']] for r in valid])
    hips=ps[:,[23,24]].mean(1); wrists=ps[:,[15,16]].mean(1)
    body=np.maximum(np.linalg.norm(ps[:,11]-ps[:,23],axis=1),20)
    rel=(wrists-hips)/body[:,None]
    dt=np.diff(ts); vel=np.linalg.norm(np.diff(rel,axis=0),axis=1)/np.maximum(dt,.001)
    vel[dt>.2]=0
    vel=np.convolve(vel,np.ones(3)/3,mode='same')
    candidates=[]
    # Top = hands raised, followed by rapid descent to hip height.
    for j in range(2,len(valid)-3):
        if not (rel[j,1] <= min(rel[j-1,1],rel[j+1,1]) and rel[j,1]<-.65):
            continue
        window=np.where((ts>ts[j]+.08)&(ts<ts[j]+1.15))[0]
        if not len(window):
            continue
        impact=int(min(window,key=lambda k: abs(rel[k,1]-.12)-min(vel[min(k,len(vel)-1)],5)*.025))
        if ts[impact]-ts[j]>.85:
            continue
        score=(rel[impact,1]-rel[j,1])*max(vel[max(0,j):impact],default=0)
        candidates.append((score,j,impact))
    if not candidates:
        missing['impact']=estimate(manual_impact,.95,'user_annotation','人工指定' if manual_impact is not None else '未找到完整上杆到下杆序列',unit='s') if manual_impact is not None else missing['impact']
        return missing
    score,top,impact=max(candidates)
    if manual_impact is not None:
        impact=int(np.argmin(abs(ts-manual_impact)))
        before=np.where((ts<manual_impact)&(ts>manual_impact-1.5))[0]
        if len(before):
            top=int(before[np.argmin(rel[before,1])])
    pre=np.where((ts<ts[top])&(ts>ts[top]-2.))[0]
    address=int(pre[np.argmax(rel[pre,1])]) if len(pre) else max(0,top-1)
    post=np.where((ts>ts[impact]+.5)&(ts<ts[impact]+3.))[0]
    finish=int(min(post,key=lambda k: np.mean(vel[max(0,k-3):min(len(vel),k+3)]))) if len(post) else len(valid)-1
    conf=float(min(.65,max(.15,score/30)))
    indices={'address':address,'takeaway':min(top,address+max(1,(top-address)//5)), 'backswing':(address+top)//2,'top':top,'downswing':(top+impact)//2,'impact':impact,'follow_through':min(finish,impact+max(1,(finish-impact)//3)),'finish':finish}
    out={n:estimate(float(ts[k]),conf,'body_relative_wrist_extrema_2d',unit='s',frame=valid[k]['frame']) for n,k in indices.items()}
    out['impact']['reason']='手腕最低区间近似；未由球离座确认，不能视为精确接触帧'
    out['impact']['confidence']=min(conf,.4)
    if manual_impact is not None:
        out['impact']=estimate(manual_impact,.95,'user_annotation',unit='s',frame=valid[impact]['frame'])
    return out
