from pathlib import Path
from .io import dump
from .pose import extract


def run(a,cfg,video,meta):
    rows,selection = extract(video,cfg['pose'],Path(__file__).parents[1]/'models')
    dump(a.out/'pose.json', {'coordinate_system':'normalized video pixels, origin top-left','selection':selection,'frames':rows})
    from .render import render
    render(video,a.out/'overlay.mp4', rows, {}, [], a, None)
