from pathlib import Path
from .io import dump
from .pose import extract


def run(a,cfg,video,meta):
    rows,selection = extract(video,cfg['pose'],Path(__file__).parents[1]/'models')
    dump(a.out/'pose.json', {'coordinate_system':'normalized video pixels, origin top-left','selection':selection,'frames':rows})
    from .phases import segment
    phases = segment(rows,a.impact_time) if a.stage>=2 else {}
    from .ball import track
    balls = track(video,rows,phases,cfg['ball'],a.ball_roi) if a.stage>=3 else {}
    dump(a.out/'ball_track.json', balls)
    if balls.get('events',{}).get('impact') and a.impact_time is None:
        phases['impact']=balls['events']['impact']
    from .distance import layered
    distance=layered(balls,a.view,cfg['ball'],cfg['physics'],a.camera_distance) if a.stage>=4 else {}
    dump(a.out/'swing_metrics.json', {'phases':phases,'distance':distance})
    from .render import render
    render(video,a.out/'overlay.mp4', rows, phases, balls, a, None)
