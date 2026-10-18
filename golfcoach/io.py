import json
import subprocess
from pathlib import Path
import cv2


def dump(path, obj):
    Path(path).write_text(json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')


def probe(path):
    p = subprocess.run(['ffprobe', '-v', 'error', '-show_streams', '-show_format', '-of', 'json', str(path)], capture_output=True, text=True, check=True)
    data = json.loads(p.stdout)
    s = next(s for s in data['streams'] if s['codec_type'] == 'video')
    # Deliberately exclude device serial/location metadata from outputs.
    return {k: s.get(k) for k in ['codec_name','width','height','avg_frame_rate','duration','color_transfer','side_data_list']}


def normalize(src, dst, cfg):
    meta = probe(src)
    vf = []
    if meta.get('color_transfer') in ('arib-std-b67','smpte2084'):
        vf += ['zscale=t=linear:npl=100', 'format=gbrpf32le', 'zscale=p=bt709', 'tonemap=tonemap=hable:desat=0', 'zscale=t=bt709:m=bt709:r=tv']
    w = cfg['max_width']
    vf += [f"scale='min({w},iw)':-2", 'setsar=1']
    # ffmpeg autorotates before filtering. Preserve input frame rate; no 30fps resample.
    subprocess.run(['ffmpeg','-y','-v','error','-i',str(src),'-map','0:v:0','-an','-vf',','.join(vf),'-c:v','libx264','-preset','fast','-crf','18','-pix_fmt','yuv420p','-map_metadata','-1',str(dst)], check=True)
    return meta


def frames(path):
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise RuntimeError(f'无法解码视频: {path}')
    fps = cap.get(cv2.CAP_PROP_FPS)
    if fps <= 0:
        raise RuntimeError('无有效帧率')
    i = 0
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            # normalized H264 timestamps are monotonic, including VFR.
            t = cap.get(cv2.CAP_PROP_POS_MSEC) / 1000
            yield i, t, frame
            i += 1
    finally:
        cap.release()
