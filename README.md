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

## Step 7：合成视频

`--stage 7` 合成 H264/yuv420p、骨架、候选球圈、有效飞行段、事件、低置信度杆身线、阶段置信度、中文结论及距离降级说明；生成 keyframes/address、top、impact、finish.jpg。击前球圈灰色、击后黄色；不跨丢帧连线。中文字体自动查找 macOS/Windows/Noto CJK，Linux 可设置 `GOLF_FONT=/path/font.ttc`；没有字体则视频显示英文降级提示，中文仍完整保留在报告。`--keep-audio` 保留第一条原音轨。未检测出的阶段不伪造截图。

## Step 8：失败和降级

`--stage 8` 与完整运行均启用保守降级。未检测项目为 null + reason；错误写 failure.json。球轨迹点不能外推成撞网/落地；无深度、无尺度不报米数。HDR 转换优先 zscale；ffmpeg 无该滤镜时保留矩阵转换并写明确质量警告。Mac 的 MediaPipe 即使 CPU 也初始化 OpenGL，在受限沙箱/无显示服务可能失败；正常桌面终端可跑，CPU 推理由 XNNPACK 执行。

验证：`python -m pytest -q`，覆盖无姿态、无球、正面拒绝距离、尺度单位、低置信度禁止建议。参数集中在 config.yaml。每个估计都有 method/confidence；模型置信度及工程质量分不是经数据集校准的概率。

完整运行：

```bash
python analyze_golf.py --video /path/iphone.mov --handedness right --view 45deg --out output
# 查看中文交互式视频报告（无需 Web 框架）
python -m http.server 8000 --directory output
# 浏览器访问 http://localhost:8000/report.html
```

严格复现可用 `pip install -r requirements.lock.txt`（锁文件来自 Apple Silicon / Python3.11；其他平台优先 requirements.txt）。预训练权重：[MediaPipe Pose Landmarker 官方说明](https://ai.google.dev/edge/mediapipe/solutions/vision/pose_landmarker/python)，代码中固定 full/float16/1 下载地址；也可手动放到 models/pose_landmarker_full.task。代码 MIT，依赖和模型适用各自许可证。

输出 pose.json 为逐帧像素坐标/置信度/时间戳；ball_track.json 为击球窗口的逐帧候选、速度（px/s）、丢失区间和有效段，窗口外未分析；swing_metrics.json 包含阶段、动作指标、三层距离及质量。`normalized.mp4` 是本地规范化缓存，不含音频。原视频/分析视频/关键帧均被 Git 忽略，默认只本地保存。

稳像/质量模块以稀疏背景光流 + RANSAC 估计手机晃动/变焦；明显晃动时禁止把鼻尖像素位移解释成头部动作，并拒绝平面距离。输出曝光极值像素比例、姿态覆盖率；这些质量分是工程评分。未做畸变校正、精确深度或真实杆面估计。

提高精度：手机固定、侧面拍全身/球/杆头，尽量120fps以上；球与背景对比清楚；避免投影白点和过曝；保留完整准备—上杆—击球—收杆；一段一杆。30fps 高速小球可能帧间直接消失，增加模型复杂度无法恢复根本没被拍到的信息。

## Step 9：真实视频实测（2026-10-18）

输入为用户提供的 IMG_9651.MOV：63.29 秒、1898 帧、约30fps、1920×1080 HEVC Main10/HLG、带 -90° 显示旋转。输出为1080×1920 H264/yuv420p，约63.33秒；规范化恒帧率编码产生约0.04秒尾部差异。片中包含多次挥杆，默认选择运动得分最高的一次；建议单杆裁剪，或用人工 impact-time 指定目标。

在 Apple M1 / Python3.11 / CPU XNNPACK / pose stride=2 上，完整 CLI 实测 **122.41秒**（权重已下载，不含首次安装）。阶段与视频输出均实际生成，8项自动测试通过；产物验证：

```bash
python scripts/check_outputs.py output-real
```

- 姿态覆盖 **99.10%（1881/1898帧）**，球手身份评分0.8。目视复核 address/top/impact/finish 骨架基本贴合；快速手腕、转身遮挡仍可能偏移。
- Address **41.975s**、Top **43.844s**、Impact 近似 **44.111s**、Finish **44.845s**。修复后的两次独立姿态推理/分割中，全部阶段时间差为 **0.000秒**；这是本例复现结果，不保证任意视频同等准确。Impact 仍为手腕代理，置信度0.4，不是接触传感器测量。
- 本杆报告测得：准备到 impact 近似时刻鼻尖移动 **51.65px / 0.357躯干长度**（置信度0.4），顶点领先臂夹角 **156.94°**（0.5），收杆后髋/踝相对波动 **0.082躯干长度**（0.5）。报告给出对应帧号、纠正练习，以及领先臂较伸展的正面观察。没有把人体像素换成假厘米。
- 能检测草垫上的真实白球（半径约8.6px）；发现并修复了黄/白颜色掩膜合并草垫导致漏球的问题。
- **本例未通过“连续击后轨迹”验收**：高速拖影与30fps短飞行导致有效击后点不足3个。没有可靠轨迹线，也没有确认撞网；Layer1距离/飞行时间、Layer2球速/杆速均为null，报告写明原因。Layer3不输出carry。不能把这次运行宣传成可靠测距成功。
- 本机 ffmpeg 没有 zscale，实际走色彩矩阵降级并降低球候选置信度；HLG高光/颜色仍有偏差。建议装带libzimg/zscale的ffmpeg后复跑。

验收状态：本例的视频生成、姿态与中文量化报告、失败降级、重复时间戳已验证；击后轨迹和米制距离仍未验证成功。后续优先增加高帧率、短曝光的真实标注数据与独立球检测器，评估召回和误检后替换颜色候选；不要用插值补出不存在的飞行帧。单元测试中的合成球仅用于算法回归，绝不作为示例实测轨迹。

每个 Step 0–9 均有独立 Git 提交；`--stage N` 运行到对应阶段。`golfcoach.pipeline.finish_analysis` 为后续本地上传页面保留服务接口；当前优先CLI与静态HTML报告，无需外部账号/API。
