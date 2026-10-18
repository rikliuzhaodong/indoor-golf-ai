import numpy as np
from .phases import estimate


def layered(ball,view,cfg,physics,camera_distance=None):
    assumptions=['针孔相机；无镜头/内参标定；球直径 42.67mm；球与背景颜色候选可能混淆', '平面位移假设飞行近似平行成像面、相机固定、深度近似恒定；不是三维距离，不是球到网真实距离', '撞网/出画无法仅凭消失区分；最后可靠观测点不是落点']
    missing=lambda reason,unit:estimate(method='insufficient_observation',reason=reason,unit=unit)
    out={'assumptions':assumptions,'layer1':{'observed_planar_displacement':missing('没有足够有效球轨迹','m'),'flight_time':missing('没有可靠离座和最后观测时间','s'),'three_dimensional_displacement':missing('无相机标定/深度观测','m')},'layer2':{'clubhead_speed':missing('杆头身份不可靠；不把手腕速度当杆头速度','m/s'),'clubhead_speed_mph':missing('杆头身份不可靠','mph'),'ball_speed':missing('无可靠尺度和轨迹','m/s'),'launch_angle_image':missing('球轨迹不足','deg'),'wrist_or_face_orientation':missing('杆身直线不能确定杆面/手腕旋转','deg')},'layer3':{'outdoor_carry':missing('默认关闭；需要可靠初速度、地面发射角与旋转，当前未达到质量门槛','m'),'warning':'模型估算，不是测距仪结果；室内撞网不是落点'}}
    seg=ball.get('segments',[])
    if not seg: return out
    points=seg[0]['points']; first,last=points[0],points[-1]
    anchor=ball['anchor']['position']; end=last['position']
    dt=last['timestamp']-ball['events']['impact']['value']
    out['layer1']['flight_time']=estimate(dt,.3,'last_seen_minus_first_departure','只是可见飞行时间；击球时间有约一帧误差',unit='s')
    delta=np.array([end['x']-anchor['x'],end['y']-anchor['y']])
    out['layer2']['launch_angle_image']=estimate(float(np.degrees(np.arctan2(-delta[1],abs(delta[0])))),.2,'image_displacement_angle','相对画面水平，非地面发射角',unit='deg')
    diam=np.array(ball.get('scale_samples_diameter_px',[]))
    if len(diam)<3 or float(np.median(diam))<cfg['min_scale_diameter_px']:
        out['layer1']['observed_planar_displacement']['reason']='稳定球直径样本不足或球直径小于尺度分辨率阈值'
        return out
    cv=float(np.std(diam)/np.mean(diam))
    scale=cfg['diameter_m']/float(np.median(diam))
    out['scale']=estimate(scale,.3,'known_ball_diameter_over_median_pixels',unit='m/pixel',diameter_cv=cv,sample_count=len(diam))
    if cv>cfg['max_scale_cv'] or view in ('front','unknown'):
        out['layer1']['observed_planar_displacement']['reason']='直径波动过大或正面/未知机位使深度变化不可辨识'
        return out
    flight_d=np.array([2*r['position']['radius'] for r in points])
    if np.max(abs(flight_d/np.median(diam)-1))>.3:
        out['layer1']['observed_planar_displacement']['reason']='飞行球直径变化超过30%，恒深平面模型不适用'
        return out
    displacement=float(np.linalg.norm(delta)*scale)
    out['layer1']['observed_planar_displacement']=estimate(displacement,.2,'ball_diameter_constant_depth_plane','尺度候选未人工确认；只代表观测平面投影，可能明显低估深度方向位移',unit='m',sensitivity_interval_m=[displacement*.5,displacement*1.5])
    times=np.array([r['timestamp'] for r in points]); xy=np.array([[r['position']['x'],r['position']['y']] for r in points])
    if len(points)>=4 and np.min(np.diff(times))>0:
        speed=float(np.median(np.linalg.norm(np.diff(xy,axis=0),axis=1)/np.diff(times))*scale)
        out['layer2']['ball_speed']=estimate(speed,.2,'median_planar_finite_difference','观测平面速度，非真实三维初速度',unit='m/s')
    return out
