from pathlib import Path
from .io import dump
from .pose import extract


def run(a,cfg,video,meta):
    rows,selection = extract(video,cfg['pose'],Path(__file__).parents[1]/'models')
    dump(a.out/'pose.json', {'coordinate_system':'normalized video pixels, origin top-left','selection':selection,'frames':rows})
    from .phases import segment
    phases = segment(rows,a.impact_time) if a.stage>=2 else {}
    dump(a.out/'swing_metrics.json', {'phases':phases})
    from .render import render
    render(video,a.out/'overlay.mp4', rows, phases, [], a, None)
