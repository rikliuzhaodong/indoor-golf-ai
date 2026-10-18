import numpy as np
from .phases import estimate


def angle(a,b,c):
    u=a-b;v=c-b
    den=np.linalg.norm(u)*np.linalg.norm(v)
    return float(np.degrees(np.arccos(np.clip(np.dot(u,v)/den,-1,1)))) if den>1e-6 else None


def calculate(rows,phases,handedness,view):
    out={}
    lead=0 if handedness=='right' else 1
    def at(name):
        t=phases.get(name,{}).get('value')
        if t is None: return None
        row=min(rows,key=lambda r:abs(r['timestamp']-t))
        if abs(row['timestamp']-t)>.15 or not row['landmarks']: return None
        return row
    def points(row,ids):
        if row is None or min(row['landmarks'][j]['confidence'] for j in ids)<.5: return None
        return np.array([[p['x'],p['y']] for p in row['landmarks']])
    def put(name,value,phase,method,unit,reason=None,conf=.5):
        ph=phases.get(phase,{})
        out[name]=estimate(value,min(conf,ph.get('confidence',0)) if value is not None else 0,method,reason,unit,phase=phase,timestamp=ph.get('value'),frame=ph.get('frame'))
    addr=at('address');top=at('top');impact=at('impact');finish=at('finish')
    p=points(addr,[11,12,23,24,25,26,27,28])
    if p is not None:
        hips=p[[23,24]].mean(0);shoulders=p[[11,12]].mean(0)
        body=max(np.linalg.norm(shoulders-hips),1)
        stance=float(np.linalg.norm(p[27]-p[28])/body)
        spine=float(np.degrees(np.arctan2(abs(shoulders[0]-hips[0]),abs(shoulders[1]-hips[1]))))
        knee=angle(p[23+lead],p[25+lead],p[27+lead])
        put('stance_width_torso_ratio',stance,'address','ankle_distance_over_torso_2d','torso')
        put('lead_knee_flexion_deg',180-knee if knee is not None else None,'address','180_minus_hip_knee_ankle_angle_2d','deg')
        put('spine_tilt_image_deg',spine,'address','hip_shoulder_line_from_image_vertical','deg','2D 投影，不是实际前倾角')
    else:
        for k,u in [('stance_width_torso_ratio','torso'),('lead_knee_flexion_deg','deg'),('spine_tilt_image_deg','deg')]: put(k,None,'address','2d_pose',u,'准备阶段关节不可靠')
    tp=points(top,[11,12,13+lead,15+lead,23,24])
    if tp is not None:
        elbow=angle(tp[11+lead],tp[13+lead],tp[15+lead])
        shoulder=tp[12]-tp[11]; hip=tp[24]-tp[23]
        sep=float(abs((np.degrees(np.arctan2(shoulder[1],shoulder[0])-np.arctan2(hip[1],hip[0]))+90)%180-90))
        body=max(np.linalg.norm(tp[[11,12]].mean(0)-tp[[23,24]].mean(0)),1)
        wrist_height=float((tp[15+lead,1]-tp[12-lead,1])/body)
        put('lead_arm_top_angle_deg',elbow,'top','shoulder_elbow_wrist_2d','deg','不能仅凭2D确定提前屈臂')
        put('x_factor_projected_deg',sep,'top','shoulder_hip_projected_line_difference','deg','仅图像线夹角，不能作为真实轴向 X-Factor',.2)
        put('top_wrist_relative_trail_shoulder',wrist_height,'top','wrist_y_minus_trail_shoulder_y_over_torso','torso','正值为手腕在肩下方；无法从2D确定上杆长度',.35)
    else:
        for k,u in [('lead_arm_top_angle_deg','deg'),('x_factor_projected_deg','deg'),('top_wrist_relative_trail_shoulder','torso')]: put(k,None,'top','2d_pose',u,'顶点阶段关节不可靠')
    ip=points(impact,[0,11,12,23,24,27,28]);ap=points(addr,[0,11,12,23,24,27,28])
    if ip is not None and ap is not None:
        body=max(np.linalg.norm(ap[[11,12]].mean(0)-ap[[23,24]].mean(0)),1)
        delta=ip[0]-ap[0]
        put('head_displacement_address_impact_px',float(np.linalg.norm(delta)),'impact','nose_pixel_displacement','px','含相机运动与透视影响')
        put('head_displacement_torso_ratio',float(np.linalg.norm(delta)/body),'impact','nose_displacement_over_address_torso','torso','未做相机运动补偿，不转换为厘米')
        def hip_fraction(q):
            span=q[28,0]-q[27,0]
            return float((q[[23,24],0].mean()-q[27,0])/span) if abs(span)>body*.2 else None
        f0,f1=hip_fraction(ap),hip_fraction(ip)
        put('hip_projection_shift_fraction',f1-f0 if f0 is not None and f1 is not None else None,'impact','hip_x_projection_between_anatomical_ankles','foot_span','不是足底压力/真实重心；脚在画面重合时不可用',.25)
    else:
        for k,u in [('head_displacement_address_impact_px','px'),('head_displacement_torso_ratio','torso'),('hip_projection_shift_fraction','foot_span')]: put(k,None,'impact','2d_pose',u,'准备/击球阶段关节不可靠')
    # Compare early downswing to top, not a claim of measured club path.
    dp=points(at('downswing'),[11,12,15,16,23,24])
    if tp is not None and dp is not None:
        body=max(np.linalg.norm(tp[[11,12]].mean(0)-tp[[23,24]].mean(0)),1)
        shift=float(((dp[[15,16],0].mean()-dp[[23,24],0].mean())-(tp[[15,16],0].mean()-tp[[23,24],0].mean()))/body)
        put('downswing_hand_lateral_change',shift,'downswing','body_relative_wrist_lateral_change_2d','torso','机位未标定，不能单独据此诊断 over-the-top',.2)
    else: put('downswing_hand_lateral_change',None,'downswing','2d_proxy','torso','关节不足')
    ft=phases.get('finish',{}).get('value')
    samples=[r for r in rows if ft is not None and ft<=r['timestamp']<=ft+.5 and r['landmarks']]
    values=[]
    for r in samples:
        q=points(r,[11,12,23,24,27,28])
        if q is not None:
            body=max(np.linalg.norm(q[[11,12]].mean(0)-q[[23,24]].mean(0)),1)
            values.append((q[[23,24]].mean(0)-q[[27,28]].mean(0))/body)
    enough=len(samples)>3 and samples[-1]['timestamp']-samples[0]['timestamp']>=.35
    put('finish_sway_torso_ratio',float(np.linalg.norm(np.std(values,axis=0))) if enough and len(values)>3 else None,'finish','std_hip_relative_ankles_0_5_seconds','torso','结束后约0.5秒稳定性，非真实平衡力测量')
    return out
