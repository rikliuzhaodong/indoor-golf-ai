from pathlib import Path
from .io import dump
from .pose import extract


def run(a,cfg,video,meta):
    rows,selection = extract(video,cfg['pose'],Path(__file__).parents[1]/'models')
    finish_analysis(a,cfg,video,meta,rows,selection)


def finish_analysis(a,cfg,video,meta,rows,selection):
    """Reusable service boundary for local upload UIs and module iteration."""
    dump(a.out/'run_config.json', {'config':cfg,'handedness':a.handedness,'view':a.view,'stage':a.stage,'manual_impact':a.impact_time,'camera_distance':a.camera_distance,'ball_roi':a.ball_roi,'model':'mediapipe_pose_full_float16_v1','local_processing':True})
    dump(a.out/'pose.json', {'coordinate_system':'normalized video pixels, origin top-left','selection':selection,'frames':rows})
    from .phases import segment
    phases = segment(rows,a.impact_time) if a.stage>=2 else {}
    from .ball import track
    balls = track(video,rows,phases,cfg['ball'],a.ball_roi) if a.stage>=3 else {}
    if meta.get('hdr_conversion')=='matrix_only_fallback':
        for r in balls.get('frames',[]): r['confidence']*=.7
        if balls.get('quality'): balls['quality']['confidence']*=.7
    if balls.get('events',{}).get('impact') and a.impact_time is None:
        phases['impact']=balls['events']['impact']
    dump(a.out/'ball_track.json', balls)
    from .distance import layered
    distance=layered(balls,a.view,cfg['ball'],cfg['physics'],a.camera_distance) if a.stage>=4 else {}
    from .metrics import calculate
    metrics=calculate(rows,phases,a.handedness,a.view) if a.stage>=5 else {}
    from .quality import assess
    analysis_quality=assess(video,rows) if a.stage>=8 else {}
    camera_motion=analysis_quality.get('camera_motion',{}).get('value')
    if camera_motion is not None and camera_motion>cfg['quality']['camera_motion_threshold']:
        for name in ['head_displacement_torso_ratio','head_displacement_address_impact_px']:
            if name in metrics:
                metrics[name]['confidence']=min(metrics[name]['confidence'],.15)
                metrics[name]['reason']='相机晃动或变焦；未补偿，不能归因于头部动作'
        measure=distance.get('layer1',{}).get('observed_planar_displacement')
        if measure:
            measure.update(value=None,confidence=0.,reason='相机晃动/变焦，像素尺度不可靠')
    dump(a.out/'swing_metrics.json', {'phases':phases,'distance':distance,'metrics':metrics,'analysis_quality':analysis_quality})
    from .coaching import generate,write_report
    quality=[f'挥杆者身份置信度：{selection["confidence"]:.2f}',f'球跟踪：{balls.get("quality",{})}']
    if selection.get('reason'): quality.append(selection['reason'])
    quality += [f'{k}: {v}' for k,v in analysis_quality.items()]
    if meta.get('warning'): quality.append(meta['warning'])
    coach=generate(metrics,phases,quality,cfg.get('coaching')) if a.stage>=6 else None
    from .render import render
    render(video,a.out/'overlay.mp4', rows, phases, balls, a, coach, distance)

    if coach: write_report(a.out,coach,phases,distance,metrics,quality)
