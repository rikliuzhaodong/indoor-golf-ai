from html import escape
from .io import dump


def generate(metrics,phases,quality):
    tips=[];good=[]
    def evidence(k):
        m=metrics.get(k,{})
        if m.get('value') is None or m.get('confidence',0)<.25: return None
        return m
    def add(k,threshold,phenomenon,fix,drill,invert=False):
        m=evidence(k)
        if m and ((m['value']<threshold) if invert else (m['value']>threshold)):
            tips.append({'phenomenon':phenomenon,'evidence':f"{m['phase']} @ {m['timestamp']:.3f}s / 帧 {m['frame']}：{m['value']:.3f} {m['unit']}，置信度 {m['confidence']:.2f}",'metric':k,'correction':fix,'drill':drill,'confidence':m['confidence'],'method':'conservative_2d_rules'})
    add('head_displacement_torso_ratio',.18,'准备到击球近似时刻头部投影移动较大','固定手机后，尝试让头部保持在准备位置附近；不要刻意锁死颈部','下一杆做半挥杆，在 address/impact 关键帧比较鼻尖位置。')
    add('lead_arm_top_angle_deg',145,'顶点领先臂在画面中弯曲较明显','缩短上杆到领先臂能自然伸展的位置，保持放松','下一杆做三次慢速上杆停顿，复查顶点肩—肘—腕夹角。',True)
    add('finish_sway_torso_ratio',.045,'结束姿势的髋部相对双踝仍明显晃动','降低挥杆力度，让结束姿势自然站稳','下一杆以七成力度击球，收杆后保持2秒，再比较 finish 后0.5秒髋部波动。')
    add('top_wrist_relative_trail_shoulder',.15,'顶点领先手腕在画面中低于后侧肩','先确认是否为刻意短杆；全挥时用慢速上杆检查手臂抬升','下一杆做上杆顶点停顿，对照 top 截图中的手腕和后侧肩。')
    for k,limit,text in [('finish_sway_torso_ratio',.045,'收杆后髋部相对双踝的投影较稳定'),('head_displacement_torso_ratio',.18,'准备至击球近似时刻头部投影位移较小')]:
        m=evidence(k)
        if m and m['value']<=limit:
            good.append(f"{text}：{m['value']:.3f} {m['unit']}（{m['phase']}，帧 {m['frame']}）。")
    if not tips:
        summary='这一杆的可靠二维指标尚未触发明确纠正阈值；请结合关键帧复核，不能据此判断没有问题。'
    else: summary='这一杆优先复核：'+tips[0]['phenomenon']+'（二维投影观察）。'
    if not good:
        good=['目前没有足够可靠证据给出做得好的技术结论；保留空缺，避免编造表扬。']
    return {'summary':summary,'corrections':tips[:3],'positive':good[:1],'quality':quality,'method':'rules_from_measured_2d_metrics','limitations':['2D投影不等于三维旋转、足底压力或杆面角；未补偿手持晃动/变焦。','阶段是启发式估计，impact 若非球离座确认，动作建议需核对对应帧。','室内短飞行、30fps/遮挡/过曝可能导致球和距离不可用。']}


def write_report(out,coach,phases,distance,metrics,quality):
    lines=['# 本杆室内挥杆分析','',coach['summary'],'','## 优先纠正']
    for i,t in enumerate(coach['corrections'],1):
        lines += [f"{i}. **{t['phenomenon']}** → {t['evidence']} → {t['correction']} → {t['drill']}"]
    if not coach['corrections']: lines+=['未发现足够可靠的可执行纠正证据。']
    lines+=['','## 做得好的地方',*coach['positive'],'','## 关键帧与阶段']
    for name,p in phases.items():
        if p['value'] is None: lines += [f"- {name}：无法检测；{p['reason']}"]
        else:
            lines += [f"- {name}：{p['value']:.3f}s，帧 {p.get('frame','?')}，confidence={p['confidence']:.2f}，method={p['method']}"]
            if name in ['address','top','impact','finish']:
                lines += [f'![{name}](keyframes/{name}.jpg)']
    lines+=['','## 动作指标']
    for k,m in metrics.items(): lines += [f"- {k}：{m['value']} {m['unit']}；confidence={m['confidence']:.2f}；method={m['method']}；{m.get('reason') or ''}"]
    lines+=['','## 距离（分层；null 表示不可靠）']
    for layer in ['layer1','layer2','layer3']:
        lines += [f'### {layer}']
        for k,m in distance.get(layer,{}).items():
            if isinstance(m,dict): lines += [f"- {k}：{m['value']} {m['unit']}；confidence={m['confidence']:.2f}；method={m['method']}；{m.get('reason') or ''}"]
            else: lines += [f'**{m}**']
    lines+=['','## 相机与尺度假设',*['- '+s for s in distance.get('assumptions',[])],'','## 分析质量/失败原因',*['- '+s for s in quality],'','## 分析局限',*['- '+s for s in coach['limitations']]]
    text='\n'.join(lines)+'\n'
    (out/'report.md').write_text(text,encoding='utf-8')
    # Dependency-free safe HTML; no script or remote resource.
    import re
    html=[]
    for line in lines:
        m=re.fullmatch(r'!\[([^]]+)\]\((keyframes/[a-z_]+\.jpg)\)',line)
        if m: html.append(f'<img src="{m[2]}" alt="{escape(m[1])}" style="max-width:360px">')
        elif line.startswith('#'): html.append('<h3>'+escape(line.lstrip('# '))+'</h3>')
        else: html.append('<p>'+escape(line)+'</p>')
    (out/'report.html').write_text('<!doctype html><meta charset="utf-8"><title>本杆分析</title><style>body{max-width:1000px;margin:30px auto;font:16px system-ui;line-height:1.7;padding:20px}video{max-width:100%;max-height:700px}h3{margin-top:32px}p{overflow-wrap:anywhere}</style><video controls src="overlay.mp4"></video>'+''.join(html),encoding='utf-8')
    dump(out/'coaching.json',coach)
