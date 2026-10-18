import cv2
import numpy as np
from .io import frames
from .phases import estimate


def assess(video,poses):
    motion=[];exposure=[];prev=None
    for i,t,im in frames(video):
        if i%15: continue
        small=cv2.resize(im,(270,480))
        gray=cv2.cvtColor(small,cv2.COLOR_BGR2GRAY)
        exposure.append(float(np.mean((gray<8)|(gray>247))))
        if prev is not None:
            p=cv2.goodFeaturesToTrack(prev,150,.02,12)
            if p is not None:
                q,status,_=cv2.calcOpticalFlowPyrLK(prev,gray,p,None)
                if q is not None and np.sum(status)>12:
                    good=status[:,0].astype(bool)
                    m,inliers=cv2.estimateAffinePartial2D(p[good],q[good],method=cv2.RANSAC,ransacReprojThreshold=2.)
                    if m is not None and inliers is not None and np.mean(inliers)>.5:
                        move=float(np.hypot(m[0,2],m[1,2])/np.hypot(270,480))
                        zoom=float(abs(np.hypot(m[0,0],m[1,0])-1))
                        motion.append(max(move,zoom))
        prev=gray
    coverage=sum(bool(r['landmarks']) for r in poses)/max(1,len(poses))
    movement=float(np.percentile(motion,90)) if motion else None
    return {'pose_coverage':estimate(coverage,.8,'fraction_frames_with_selected_pose',unit='fraction'), 'camera_motion':estimate(movement,.5 if motion else 0.,'sparse_background_ransac_affine_p90','>0.01 提示晃动/变焦；未对关键点做稳像',unit='image_diagonal_fraction'), 'clipped_exposure_fraction':estimate(float(np.mean(exposure)) if exposure else None,.5,'gray_extremes_fraction','仅亮暗像素比例，不是曝光计量',unit='fraction')}
