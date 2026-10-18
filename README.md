# 室内高尔夫 AI 教练

Python 3.10–3.12 / CPU，本地运行。当前为保守的计算机视觉 MVP；低质量项目返回 null 和原因，不编造轨迹或码数。

## Step 0：环境与视频读取

安装 Python 3.11、ffmpeg（必须带 zscale/libx264），然后：

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python analyze_golf.py --video /path/iphone.mov --stage 0 --out output
```

验证 `output/normalized.mp4` 和 `input_info.json`。支持 iPhone HEVC、旋转及 HDR 转 SDR；需要 ffmpeg。首轮需联网下载公开姿态权重，之后离线。输入原视频及 GPS 元数据不会上传或提交。
