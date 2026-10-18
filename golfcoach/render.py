import os
from pathlib import Path
import subprocess
import textwrap
import cv2
import numpy as np
from PIL import Image,ImageDraw,ImageFont
from .io import frames
from .pose import draw


def font_path():
    options=[os.environ.get('GOLF_FONT',''),'/System/Library/Fonts/STHeiti Light.ttc','C:/Windows/Fonts/msyh.ttc','/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc']
    return next((p for p in options if p and Path(p).exists()),None)


def render(video,out,poses,phases,track,a,summary,distance=None):
    cap=cv2.VideoCapture(str(video))
    fps=cap.get(cv2.CAP_PROP_FPS); w=int(cap.get(3)); h=int(cap.get(4)); cap.release()
    tmp=out.with_name('render_silent.mp4')
    font=ImageFont.truetype(font_path(),max(16,w//45)) if font_path() else None
    panel=None
    if font:
        panel=Image.new('RGB',(w,150),(15,22,30)); painter=ImageDraw.Draw(panel)
        texts=[summary['summary'] if summary else '姿态与轨迹分析', '距离不可靠；详见分层报告']
        measurement=(distance or {}).get('layer1',{}).get('observed_planar_displacement',{})
        if measurement.get('value') is not None:
            texts[1]=f"平面位移估计 {measurement['value']:.2f}m，置信度 {measurement['confidence']:.2f}；不是户外距离"
        if summary and summary['corrections']:
            texts.append('优先练习：'+summary['corrections'][0]['drill'])
        y=6
        for text in texts:
            for line in textwrap.wrap(text,width=max(16,w//(max(16,w//45)))):
                painter.text((12,y),line,font=font,fill=(255,240,210));y+=max(20,w//40)
    by_frame={r['frame']:r for r in track.get('frames',[])} if isinstance(track,dict) else {}
    segments=track.get('segments',[]) if isinstance(track,dict) else []
    club={r['frame']:r for r in track.get('club',[])} if isinstance(track,dict) else {}
    key_ids={p.get('frame'):n for n,p in phases.items() if n in ('address','top','impact','finish') and p.get('value') is not None}
    (a.out/'keyframes').mkdir(exist_ok=True)
    proc=subprocess.Popen(['ffmpeg','-y','-v','error','-f','rawvideo','-pix_fmt','bgr24','-s',f'{w}x{h}','-r',str(fps),'-i','pipe:0','-an','-c:v','libx264','-preset','fast','-crf','20','-pix_fmt','yuv420p','-movflags','+faststart',str(tmp)],stdin=subprocess.PIPE)
    try:
        for i,t,im in frames(video):
            draw(im,poses[i])
            row=by_frame.get(i,{})
            if row.get('position'):
                p=row['position'];color=(180,180,180) if row.get('state')=='pre_impact' else (0,255,255)
                cv2.circle(im,(round(p['x']),round(p['y'])),max(4,round(p['radius'])),color,2)
            # Draw accepted contiguous segments only; no lines through missing frames.
            for seg in segments:
                points=[p for p in seg['points'] if p['frame']<=i]
                for u,v in zip(points,points[1:]):
                    if v['frame']-u['frame']!=1: continue
                    p,q=u['position'],v['position']
                    cv2.line(im,(round(p['x']),round(p['y'])),(round(q['x']),round(q['y'])),(0,230,255),3)
            if i in club:
                x1,y1,x2,y2=club[i]['line'];cv2.line(im,(x1,y1),(x2,y2),(200,120,20),1)
            for label,event in track.get('events',{}).items() if isinstance(track,dict) else []:
                frame=event.get('frame')
                if frame is not None and frame<=i and abs(t-event['value'])<1.2:
                    p=by_frame.get(frame,{}).get('position')
                    if p:
                        cv2.putText(im,label,(round(p['x'])+8,round(p['y'])-10),cv2.FONT_HERSHEY_SIMPLEX,.5,(255,160,0),2)
            cv2.putText(im,f'{t:.3f}s frame {i}',(20,35),cv2.FONT_HERSHEY_SIMPLEX,.7,(255,255,255),2)
            for name,p in phases.items():
                if p.get('value') is not None and abs(t-p['value'])<.12:
                    cv2.putText(im,f"{name} ~ {p['confidence']:.2f}",(20,70),cv2.FONT_HERSHEY_SIMPLEX,.8,(0,230,255),2)
            if panel:
                im[-150:]=cv2.cvtColor(np.array(panel),cv2.COLOR_RGB2BGR)
            else:
                cv2.putText(im,'Distance uncertain - see report',(20,h-35),cv2.FONT_HERSHEY_SIMPLEX,.65,(0,230,255),2)
            if i in key_ids:
                cv2.imwrite(str(a.out/'keyframes'/f'{key_ids[i]}.jpg'),im)
            proc.stdin.write(im.tobytes())
    finally:
        proc.stdin.close()
        code=proc.wait()
    if code:
        raise RuntimeError('视频编码失败')
    if a.keep_audio:
        subprocess.run(['ffmpeg','-y','-v','error','-i',str(tmp),'-i',str(a.video),'-map','0:v:0','-map','1:a:0?','-c:v','copy','-c:a','aac','-map_metadata','-1','-shortest','-movflags','+faststart',str(out)],check=True)
        tmp.unlink()
    else: tmp.replace(out)
