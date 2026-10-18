import cv2
import numpy as np
from golfcoach.ball import candidates,track
from golfcoach.phases import estimate
import yaml


def test_white_ball_not_merged_into_touching_yellow_background():
    cfg=yaml.safe_load(open('config.yaml'))['ball']
    # A white ball sitting on a green/yellow mat must remain its own contour.
    hsv=np.zeros((100,100,3),np.uint8);hsv[:]=[35,100,190]
    im=cv2.cvtColor(hsv,cv2.COLOR_HSV2BGR)
    cv2.circle(im,(50,50),7,(230,230,230),-1)
    cs=candidates(im,cfg)
    assert any(abs(c['x']-50)<2 and abs(c['y']-50)<2 for c in cs)


def test_static_ball_never_becomes_flight(tmp_path):
    cfg=yaml.safe_load(open('config.yaml'))['ball']
    path=tmp_path/'static.avi'
    writer=cv2.VideoWriter(str(path),cv2.VideoWriter_fourcc(*'MJPG'),30,(160,160))
    poses=[]
    for i in range(45):
        im=np.zeros((160,160,3),np.uint8);cv2.circle(im,(100,130),5,(240,240,240),-1);writer.write(im)
        ps=[{'x':80.,'y':80.,'confidence':1.} for _ in range(33)]
        ps[11]['y']=40.;ps[23]['y']=90.;ps[27]['y']=ps[28]['y']=120.
        poses.append({'landmarks':ps})
    writer.release()
    result=track(path,poses,{'impact':estimate(.7,.5)},cfg)
    assert result['segments']==[]
    assert 'impact' not in result['events']


def test_visible_launch_tracks_then_stops_at_loss(tmp_path):
    cfg=yaml.safe_load(open('config.yaml'))['ball']
    path=tmp_path/'launch.avi';writer=cv2.VideoWriter(str(path),cv2.VideoWriter_fourcc(*'MJPG'),30,(160,160));poses=[]
    for i in range(45):
        im=np.zeros((160,160,3),np.uint8)
        if i<22: center=(85,130)
        elif i<32: center=(85+(i-21)*5,130-(i-21)*4)
        else: center=None
        if center: cv2.circle(im,center,5,(240,240,240),-1)
        writer.write(im)
        ps=[{'x':80.,'y':80.,'confidence':1.} for _ in range(33)]
        ps[11]['y']=40.;ps[23]['y']=90.;ps[27]['y']=ps[28]['y']=120.
        poses.append({'landmarks':ps})
    writer.release()
    result=track(path,poses,{'impact':estimate(.73,.5)},cfg)
    assert len(result['segments'])==1
    points=result['segments'][0]['points']
    assert len(points)>=3
    assert all(b['position']['x']>a['position']['x'] for a,b in zip(points,points[1:]))
    assert all(r['position'] is None for r in result['frames'] if r['frame']>=32)
    assert result['events']['last_seen']['frame']<32
