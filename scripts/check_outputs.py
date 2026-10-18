"""Validate real-run artifacts without including private media in the repository."""
import argparse
import json
from pathlib import Path
import subprocess

p=argparse.ArgumentParser();p.add_argument('out',type=Path);a=p.parse_args()
for name in ['overlay.mp4','pose.json','ball_track.json','swing_metrics.json','report.md','report.html']:
    assert (a.out/name).stat().st_size>0,name
pose=json.loads((a.out/'pose.json').read_text());metrics=json.loads((a.out/'swing_metrics.json').read_text())
info=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-of','json',str(a.out/'overlay.mp4')]))
v=next(s for s in info['streams'] if s['codec_type']=='video')
assert v['codec_name']=='h264' and v['pix_fmt']=='yuv420p'
assert abs(int(v['nb_frames'])-len(pose['frames']))<=1
for name in ['address','top','impact','finish']:
    if metrics['phases'][name]['value'] is not None:
        assert (a.out/'keyframes'/f'{name}.jpg').is_file()
for layer in ['layer1','layer2']:
    for estimate in metrics['distance'][layer].values():
        assert 'confidence' in estimate and 'method' in estimate
        if estimate['value'] is None: assert estimate['reason']
print(json.dumps({'frames':len(pose['frames']),'pose_coverage':metrics['analysis_quality']['pose_coverage']['value'],'codec':v['codec_name'],'duration_seconds':v['duration'],'phases':{k:v['value'] for k,v in metrics['phases'].items()}},ensure_ascii=False,indent=2))
