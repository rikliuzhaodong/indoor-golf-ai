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

## Step 3：球与球杆

`--stage 3` 检查 ball_track.json：脚旁稳定球候选 → 离座运动候选 → 速度门控；只搜索击球前后窗口，窗口内逐帧，白球/黄球颜色、圆度和半径过滤。少于3个击后点不公布有效轨迹段；丢失超时或反向候选停止，不跨长缺口连接。`--ball-roi x,y,w,h` 可用归一化坐标限制击球区域，但应包含短飞行区域。Hough 仅尝试手边杆身线，不能证明杆头或杆面。球杆低置信度，屏幕白点/模糊小球是主要限制，后续需专门球检测器。

## Step 4：室内分层距离

`--stage 4` 查看 swing_metrics.json.distance。稳定球直径≥6px、样本≥3、直径变异≤20%，并有至少3个击后球点，才尝试 `42.67mm / 球直径像素` 恒深平面尺度；飞行直径变化>30%或 front/unknown 机位拒绝米数。Layer1 输出观测平面位移与可见时间；不是三维距离。区间仅为尺度敏感性范围，不是统计置信区间。Layer2 尝试图像发射角和平面球速（至少4点）；杆头速度/杆面方向不可可靠辨识则 null。Layer3 即使配置开启也受质量门槛约束，MVP 不产生虚假 carry。`--camera-distance` 预留为辅助输入，当前不会将单一距离升级成标定或3D结果。

## Step 5：动作指标

`--stage 5` 查看 metrics，每项带 phase、frame、timestamp、method、confidence。以髋中心/踝中心归一化，计算站宽、膝屈、图像脊柱倾角、头部位移、顶点领先臂夹角、肩髋投影夹角、髋投影转移、顶点手腕高度、下杆手部横移、收杆稳定性。左右手分别使用正确领先臂。侧/斜侧透视不能可靠恢复真实 X-Factor、压力重心、杆面或 over-the-top；只报告2D代理并标低置信度，不包装为生物力学结论。

## Step 6：中文规则建议

`--stage 6` 生成 report.md、report.html、coaching.json。最多3条，按头部移动/领先臂/收杆稳定/顶点高度筛选，包含量化证据、阶段时间、帧号、纠正和下一杆练习。低置信度不下结论；没有正面证据就明确保留，不编造表扬。阈值是保守工程启发式，不替代专业现场诊断。
