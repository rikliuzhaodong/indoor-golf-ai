import cv2
import numpy as np
from .io import frames
from .phases import estimate


def candidates(im,cfg,roi=None):
    hsv=cv2.cvtColor(im,cv2.COLOR_BGR2HSV)
    white=cv2.inRange(hsv,np.array([0,0,165]),np.array([179,90,255]))
    yellow=cv2.inRange(hsv,np.array([18,90,110]),np.array([42,255,255]))
    mask=white|yellow
    if roi is not None:
        x,y,w,h=roi
        region=np.zeros_like(mask); region[max(0,y):max(0,y+h),max(0,x):max(0,x+w)]=255
        mask &= region
    # Keep white/yellow masks separate: indoor green mats can touch the ball
    # in the yellow hue band and otherwise merge it into a giant contour.
    contours=[]
    for color_mask in [white,yellow]:
        if roi is not None: color_mask = color_mask & region
        cs,_=cv2.findContours(color_mask,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
        contours.extend(cs)
    out=[]
    for c in contours:
        area=cv2.contourArea(c); per=cv2.arcLength(c,True)
        if per==0 or area<4:
            continue
        circ=4*np.pi*area/per**2
        (x,y),r=cv2.minEnclosingCircle(c)
        if cfg['min_radius']<=r<=cfg['max_radius'] and circ>=cfg['min_circularity'] and area/(np.pi*r*r)>.42:
            out.append({'x':float(x),'y':float(y),'radius':float(r),'confidence':float(min(.75,circ*.8))})
    return out


def detect_club(im,row):
    if not row['landmarks']:
        return None
    ps=row['landmarks']; hands=np.mean([[ps[j]['x'],ps[j]['y']] for j in [15,16]],axis=0)
    if min(ps[j]['confidence'] for j in [15,16])<.5:
        return None
    gray=cv2.cvtColor(im,cv2.COLOR_BGR2GRAY)
    lines=cv2.HoughLinesP(cv2.Canny(gray,70,150),1,np.pi/180,60,minLineLength=im.shape[0]*.07,maxLineGap=12)
    choices=[]
    for l in [] if lines is None else lines[:,0]:
        a,b=np.array(l[:2]),np.array(l[2:])
        if min(np.linalg.norm(a-hands),np.linalg.norm(b-hands))<im.shape[1]*.035:
            choices.append((np.linalg.norm(a-b),l))
    if not choices:
        return None
    _,l=max(choices,key=lambda x:x[0])
    return {'line':[int(v) for v in l],'confidence':.25,'method':'hough_line_near_hands','reason':'背景直线可能混淆；不作为杆头速度或杆面方向证据'}


def track(video,poses,phases,cfg,roi_arg=None):
    impact=phases.get('impact',{}).get('value')
    out={'frames':[], 'segments':[], 'lost_intervals':[], 'events':{},'club':[], 'quality':estimate(method='color_roundness_motion_gated',reason='未检测到击球阶段')}
    if impact is None:
        return out
    start=impact-cfg['window_before']; end=impact+cfg['window_after']
    observations=[]; previous=None
    for i,t,im in frames(video):
        if t<start: continue
        if t>end: break
        h,w=im.shape[:2]
        roi=None
        if roi_arg:
            vals=[float(v) for v in roi_arg.split(',')]
            if len(vals)!=4 or any(v<0 or v>1 for v in vals) or vals[0]+vals[2]>1 or vals[1]+vals[3]>1:
                raise ValueError('ball-roi 必须为归一化 x,y,w,h 且不超出画面')
            roi=tuple(round(v*s) for v,s in zip(vals,[w,h,w,h]))
        cs=candidates(im,cfg,roi)
        gray=cv2.cvtColor(im,cv2.COLOR_BGR2GRAY)
        for c in cs:
            x,y=round(c['x']),round(c['y']); r=max(2,round(c['radius']))
            patch=(slice(max(0,y-r),min(h,y+r+1)),slice(max(0,x-r),min(w,x+r+1)))
            c['motion']=float(np.mean(cv2.absdiff(gray,previous)[patch])) if previous is not None else 0.
        observations.append((i,t,cs,im.shape,poses[i]['landmarks']))
        club=detect_club(im,poses[i])
        if club: out['club'].append(dict(frame=i,timestamp=t,**club))
        previous=gray
    # A real launch must have a stable pre-impact anchor near feet, then moving detections.
    anchors=[]
    for i,t,cs,shape,ps in observations:
        if t>impact-.04 or not ps: continue
        feet=np.mean([[ps[j]['x'],ps[j]['y']] for j in [27,28]],axis=0)
        body=abs(ps[23]['y']-ps[11]['y'])
        for c in cs:
            if feet[1]-body*.25<c['y']<feet[1]+body*.6 and abs(c['x']-feet[0])<body*1.8:
                repeats=sum(any(np.hypot(d['x']-c['x'],d['y']-c['y'])<max(3,c['radius']) for d in ds) for _,tt,ds,_,_ in observations if tt<impact-.04)
                anchors.append((repeats,c))
    if not anchors:
        out['quality']['reason']='击球前未找到脚旁稳定圆形球候选，可能分辨率/遮挡/曝光不足'
        out['frames']=[dict(frame=i,timestamp=t,position=None,confidence=0.,method='no_anchor') for i,t,*_ in observations]
        return out
    repeats,anchor=max(anchors,key=lambda v:v[0])
    if repeats<3:
        out['quality']['reason']='击球前球候选未连续稳定出现至少3帧'
        return out
    last=anchor; last_t=None; velocity=None; launched=False; segment=[]; loss_start=None; stopped=False
    stationary=[]
    for i,t,cs,_,_ in observations:
        row=dict(frame=i,timestamp=t,position=None,confidence=0.,method='no_reliable_detection',velocity_px_s=None)
        chosen=None
        if not launched and not stopped:
            near=[c for c in cs if np.hypot(c['x']-anchor['x'],c['y']-anchor['y'])<max(4,anchor['radius']*1.3)]
            if near:
                chosen=min(near,key=lambda c:np.hypot(c['x']-anchor['x'],c['y']-anchor['y']))
                stationary.append(2*chosen['radius'])
            elif t>impact-.15:
                moving=[c for c in cs if c['motion']>20 and max(5,anchor['radius']*2)<np.hypot(c['x']-anchor['x'],c['y']-anchor['y'])<350 and c['y']<anchor['y']+20 and .45< c['radius']/anchor['radius']<1.8]
                if moving:
                    chosen=min(moving,key=lambda c:np.hypot(c['x']-anchor['x'],c['y']-anchor['y']))
                    launched=True
                    out['events']['impact']=estimate(t,.55,'stationary_ball_disappearance_and_motion_candidate',unit='s',frame=i)
        elif launched and not stopped:
            dt=t-last_t
            pred=np.array([last['x'],last['y']])+(velocity*dt if velocity is not None else 0)
            moving=[c for c in cs if c['motion']>15 and .35<c['radius']/anchor['radius']<1.8 and np.linalg.norm(np.array([c['x'],c['y']])-pred)<min(260,cfg['max_speed_pixels_second']*dt)]
            if moving:
                chosen=min(moving,key=lambda c:np.linalg.norm(np.array([c['x'],c['y']])-pred))
                new_v=(np.array([chosen['x'],chosen['y']])-np.array([last['x'],last['y']]))/dt
                if velocity is not None and np.dot(new_v,velocity)<0:
                    chosen=None; stopped=True
                    out['events']['possible_net_or_reversal']=estimate(t,.2,'direction_reversal_rejected','无法确认是撞网，反向候选不连接',unit='s')
            elif dt>cfg['max_gap_seconds']:
                stopped=True
        if chosen:
            if launched and last_t is not None:
                dt=t-last_t
                velocity=(np.array([chosen['x'],chosen['y']])-np.array([last['x'],last['y']]))/dt
                row['velocity_px_s']={'x':float(velocity[0]),'y':float(velocity[1]),'confidence':.3,'method':'finite_difference_pixels'}
            row.update(position={k:chosen[k] for k in ['x','y','radius']},confidence=chosen['confidence']*.7,method='color_circle_temporal_gate',state='post_impact' if launched else 'pre_impact')
            if loss_start is not None:
                out['lost_intervals'].append({'start':loss_start,'end':t});loss_start=None
            last,last_t=chosen,t
            if launched: segment.append(row.copy())
        elif loss_start is None:
            loss_start=t
        out['frames'].append(row)
    if loss_start is not None and observations:
        out['lost_intervals'].append({'start':loss_start,'end':observations[-1][1]})
    if len(segment)>=cfg['min_track_points']:
        out['segments']=[{'points':segment,'confidence':.35,'method':'unconfirmed_color_motion_track'}]
        apex=min(segment,key=lambda r:r['position']['y'])
        out['events']['image_apex']=estimate(apex['timestamp'],.35,'minimum_image_y','图像最高点，不等于真实弹道顶点',unit='s',frame=apex['frame'])
        out['events']['last_seen']=estimate(segment[-1]['timestamp'],.35,'last_accepted_detection','未确认撞网',unit='s',frame=segment[-1]['frame'])
        out['quality']=estimate('tentative',.35,'color_circle_motion_gating','无专用球模型，轨迹待人工复核')
    else:
        # Never publish a one/two point launch as a reliable flight segment.
        out['quality']=estimate('unreliable',.1,'color_circle_motion_gating','击球后不足3个有效球点；不输出有效飞行轨迹或距离')
        out['events'].pop('impact',None)
    out['scale_samples_diameter_px']=stationary
    out['anchor']=dict(position={k:anchor[k] for k in ['x','y','radius']},confidence=.4,method='stable_round_object_near_feet')
    return out
