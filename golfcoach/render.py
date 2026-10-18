import subprocess
import cv2
from .io import frames
from .pose import draw


def render(video,out,poses,phases,track,a,summary):
    cap=cv2.VideoCapture(str(video))
    fps=cap.get(cv2.CAP_PROP_FPS); w=int(cap.get(3)); h=int(cap.get(4)); cap.release()
    tmp=out.with_name('render_silent.mp4')
    proc=subprocess.Popen(['ffmpeg','-y','-v','error','-f','rawvideo','-pix_fmt','bgr24','-s',f'{w}x{h}','-r',str(fps),'-i','pipe:0','-an','-c:v','libx264','-preset','fast','-crf','20','-pix_fmt','yuv420p','-movflags','+faststart',str(tmp)],stdin=subprocess.PIPE)
    try:
        for i,t,im in frames(video):
            draw(im,poses[i])
            cv2.putText(im,f'{t:.3f}s frame {i}',(20,35),cv2.FONT_HERSHEY_SIMPLEX,.7,(255,255,255),2)
            proc.stdin.write(im.tobytes())
    finally:
        proc.stdin.close()
        code=proc.wait()
    if code:
        raise RuntimeError('视频编码失败')
    tmp.replace(out)
