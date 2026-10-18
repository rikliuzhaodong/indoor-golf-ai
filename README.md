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

## Step 1：人体姿态

`--stage 1` 生成 `pose.json` / `overlay.mp4`。MediaPipe Tasks CPU 多人检测，按身体相对手腕运动、尺寸与中心选择一个身份，短间隔插值与 EMA 平滑。坐标为旋转、缩放后的输出视频像素。长遮挡不外推，多人身份评分接近时报告歧义。跟踪仍可能在交叉遮挡时换人；首次自动下载官方公开 full 权重。

## Step 2：阶段

`--stage 2` 写出阶段时间和对应帧。按髋中心归一化手腕高度与速度寻找上杆顶点、下杆低点与结束稳定段；长视频默认选最强的一次候选挥杆。Impact 只在球离座后才可提升置信度，手腕代理最高 0.4。可 `--impact-time 秒` 人工指定，明确标记 user_annotation；不能检测的阶段为 null。2D 阶段仍可能误判练习挥杆，关键帧必须复核。
