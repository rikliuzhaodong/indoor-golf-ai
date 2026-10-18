import argparse
from pathlib import Path
import yaml
from golfcoach.io import normalize, dump


def main():
    p = argparse.ArgumentParser(description='本地室内高尔夫挥杆分析')
    p.add_argument('--video', required=True, type=Path)
    p.add_argument('--out', type=Path, default=Path('output'))
    p.add_argument('--handedness', choices=['right','left'], default='right')
    p.add_argument('--view', choices=['side','front','45deg','unknown'], default='unknown')
    p.add_argument('--config', type=Path, default=Path(__file__).with_name('config.yaml'))
    p.add_argument('--camera-distance', type=float, help='可选相机至击球点距离（米），仅作为粗略深度辅助')
    p.add_argument('--ball-roi', help='可选击球区域 x,y,w,h，归一化 0..1，供困难画面人工约束')
    p.add_argument('--impact-time', type=float, help='可选人工击球时间（秒），不可冒充自动检测')
    p.add_argument('--keep-audio', action='store_true')
    p.add_argument('--stage', type=int, choices=range(10), default=9)
    a = p.parse_args()
    if not a.video.is_file():
        p.error('输入视频不存在')
    if a.camera_distance is not None and a.camera_distance <= 0:
        p.error('camera-distance 必须 > 0')
    if a.impact_time is not None and a.impact_time < 0:
        p.error('impact-time 必须 >= 0')
    cfg = yaml.safe_load(a.config.read_text())
    a.out.mkdir(parents=True, exist_ok=True)
    normalized = a.out/'normalized.mp4'
    print('解码、旋转与 HDR 转换…', flush=True)
    meta = normalize(a.video, normalized, cfg['video'])
    dump(a.out/'input_info.json', meta)
    if a.stage == 0:
        return
    from golfcoach.pipeline import run
    run(a, cfg, normalized, meta)


if __name__ == '__main__':
    main()
