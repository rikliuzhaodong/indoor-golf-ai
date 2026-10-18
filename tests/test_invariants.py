from golfcoach.distance import layered
from golfcoach.phases import segment,estimate
from golfcoach.metrics import angle,calculate
from golfcoach.coaching import generate
import numpy as np
import yaml


def test_no_pose_never_fabricates_phases():
    assert all(p['value'] is None and p['confidence']==0 for p in segment([]).values())


def test_missing_ball_never_emits_distance():
    cfg=yaml.safe_load(open('config.yaml'))
    d=layered({},'side',cfg['ball'],cfg['physics'])
    assert d['layer1']['observed_planar_displacement']['value'] is None
    assert d['layer3']['outdoor_carry']['value'] is None


def test_front_view_rejects_depth():
    cfg=yaml.safe_load(open('config.yaml'))
    pts=[{'frame':i,'timestamp':i*.01,'position':{'x':i*10.,'y':100-i*2.,'radius':5.}} for i in range(4)]
    ball={'segments':[{'points':pts}],'anchor':{'position':{'x':0.,'y':100.,'radius':5.}},'events':{'impact':estimate(0.,.7)},'scale_samples_diameter_px':[10]*10}
    d=layered(ball,'front',cfg['ball'],cfg['physics'])
    assert d['layer1']['observed_planar_displacement']['value'] is None
    assert '正面' in d['layer1']['observed_planar_displacement']['reason']
    d=layered(ball,'side',cfg['ball'],cfg['physics'])
    assert .12<d['layer1']['observed_planar_displacement']['value']<.14
    assert d['layer3']['outdoor_carry']['value'] is None


def test_low_confidence_does_not_trigger_coaching():
    m={'head_displacement_torso_ratio':estimate(10.,.1)}
    assert generate(m,{},[])['corrections']==[]


def test_missing_joints_are_not_zero_angles():
    m=calculate([],segment([]),'left','front')
    assert all(v['value'] is None for v in m.values())
    assert angle(np.zeros(2),np.zeros(2),np.ones(2)) is None
