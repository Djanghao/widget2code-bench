# widget-quality 评测指标文档

## 1. 工具简介

`widget-quality` 是 `widget2code-bench` 项目下的一个子包,用来**自动评估 Widget 代码生成结果的视觉质量**。输入两张图(GT 与生成图),输出一套覆盖五大维度、共 12 个指标的分数。

### 五大维度

| 维度 | 衡量什么 | 指标 |
|---|---|---|
| **Geometry** | 整图画布比例与尺寸 | `geo_score` |
| **Layout** | 内容布局结构 | `MarginAsymmetry`、`ContentAspectDiff`、`AreaRatioDiff` |
| **Legibility** | 可读性(文字与对比度) | `TextJaccard`、`ContrastDiff`、`ContrastLocalDiff` |
| **Style** | 色彩与视觉风格 | `PaletteDistance`、`Vibrancy`、`PolarityConsistency` |
| **Perceptual** | 像素/感知相似度 | `SSIM`、`LPIPS` |

### 评测流水线

```
gt.png, gen.png
     │
     ▼
 Geometry(用原始尺寸,未 resize)
     │
     ▼
 gen 被 resize 到 gt 尺寸
     │
     ├── Layout
     ├── Legibility(EasyOCR)
     ├── Perceptual(SSIM + LPIPS)
     └── Style
     │
     ▼
 composite_score:把原始值统一映射到 0–100
```

所有指标的最终分数都由 `composite.py` 的 `smooth_score` 做指数/线性/逻辑斯蒂映射,输出 **0–100** 的分值。分数越高 = 生成结果越贴近 GT。

### 入口 API

```python
from widget_quality import evaluate_pair
scores = evaluate_pair("gt.png", "gen.png")
# 或 CLI:widget-quality pair gt.png gen.png
```

---

## 2. 通用机制:`smooth_score`

```python
def smooth_score(val, scale, method="exp"):
    if method == "exp":      return 100 * exp(-val / scale)
    if method == "linear":   return 100 * max(0, 1 - val / scale)
    if method == "logistic": return 100 / (1 + exp(10 * (val - scale)))
```

**指数衰减 `exp(-x/scale)`** 是最常用的映射:
- `x = 0` → 100
- `x = scale` → 36.8
- `x = 2·scale` → 13.5
- `x = 3·scale` → 5

`scale` 越小,指标越严苛。项目中不同 metric 用了不同的 scale,下面会逐个列出。

---

## 3. Geometry:`geo_score`

### 含义
衡量生成图的**整图画布尺寸与 GT 有多接近**,综合宽高比和总面积两方面。用原图尺寸计算(不 resize)。

### 算法(geometry.py)

```python
ar_gt, ar_gen     = w_gt / h_gt,     w_gen / h_gen         # 宽高比
area_gt, area_gen = w_gt * h_gt,     w_gen * h_gen         # 画布像素总面积

ar_diff   = |log(ar_gt / ar_gen)|
area_diff = |log(area_gen / area_gt)|

aspect_score = exp(-3 · ar_diff)
size_score   = exp(-3 · area_diff)

geo = 0.6 · aspect_score + 0.4 · size_score        # ∈ [0, 1]
geo_score = 100 · geo                               # 最终分数
```

### 设计要点
- **log 比值**:尺度无关且左右对称(`|log(a/b)| = |log(b/a)|`)
- **宽高比权重(0.6)高于面积权重(0.4)**:形状比例比绝对大小更重要
- `decay=3.0`:相对宽松(`exp(-3·0.1) ≈ 74`,10% 的 AR 偏差还能拿 74 分)

### 高分条件
生成图的画布尺寸比例和总像素面积都接近 GT。整体等比缩放也能拿高分(log 比值归一化)。

### 低分情况
- 画布形状明显被拉伸/压扁(比如把方形按钮渲染成长条)
- 生成图分辨率严重偏离 GT(面积项惩罚)

---

## 4. Layout

共 3 个指标。三个指标都基于同一份 **edge mask**:

```python
edge = cv2.Canny(gray, 100, 200)
mask = cv2.dilate(edge, np.ones((3,3)))
```

即:Canny 边缘 + 3×3 膨胀,得到一张二值"内容位置"图。

### 4.1 MarginAsymmetry

#### 含义
衡量两张图**四条边距(top/right/bottom/left)的误差是否均匀**。注意:**不是衡量绝对 margin 有多准**,而是衡量"四边错得均不均"。

#### 算法

```python
# 四边 margin(像素)
m_gt  = [top_gt,  right_gt,  bottom_gt,  left_gt ]
m_gen = [top_gen, right_gen, bottom_gen, left_gen]

diffs = |m_gt - m_gen|             # 四个差值
CV    = std(diffs) / mean(diffs)   # 变异系数

score = 100 · exp(-CV / 0.5)
```

其中 `margin_from_mask`:
```python
top    = rows.min()
right  = W - cols.max()
bottom = H - rows.max()
left   = cols.min()
```
使用**原始像素数**,未做归一化。空 mask 返回 `[0,0,0,0]`。`mean < 1e-6` 时直接返回 0。

#### 关键性质
- **四边偏得一样多 → CV=0 → 满分**,即使每条边都偏了 10px
- **单边偏得离谱 → CV 很大 → 低分**
- 对 4 个数,CV 上限 ≈ 1.732(一个非零,三个零)

| 四边 diff (px) | CV | 分数 |
|---|---|---|
| [0, 0, 0, 0] | 0 | 100 |
| [10, 10, 10, 10] | 0 | 100 |
| [20, 20, 0, 0] | 1.0 | 13.5 |
| [40, 0, 0, 0] | 1.73 | 3.1 |

#### 高分条件
即使整体偏了,只要四边偏差一致(比如整体平移、等比缩放、均匀 padding 多一圈)都给高分。

#### 低分情况
单边跑飞(比如只有左边多出一大块留白),CV 飙升直接塌分。

---

### 4.2 ContentAspectDiff

#### 含义
衡量**内容区域**(edge mask 上所有非零像素的最小外接矩形)的宽高比差异。

#### 算法

```python
def bbox_ar(mask):
    ys, xs = np.where(mask > 0)
    h = ys.max() - ys.min() + 1
    w = xs.max() - xs.min() + 1
    return w / h

diff = |log(ar_gt / ar_gen)|
score = 100 · exp(-diff / 0.05)
```
任一 mask 为空 → `diff = MAX_DIFF = 5` → 分数 ≈ 0。

#### 设计要点
- **对象是"内容 bbox"**,不是整张图的 AR(整图 AR 归 Geometry)
- **log 比值**:对称、尺度无关
- **scale=0.05 非常严**:大约 5% 的 AR 偏差就掉到 40 分以下

| `ar_gen/ar_gt` | \|log\| | 分数 |
|---|---|---|
| 1.00 | 0 | 100 |
| 1.05 | 0.049 | 37.7 |
| 1.10 | 0.095 | 14.7 |
| 1.20 | 0.182 | 2.6 |
| 2.00 | 0.693 | ~0 |

#### 高分条件
内容区域形状(整体包围盒的宽高比)和 GT 一致,即使绝对大小不同。

#### 低分情况
- 生成结果内容被挤扁/拉长
- 生成图抓不到边缘(空 mask)
- bbox 被角落的噪点/压缩伪影撑大

---

### 4.3 AreaRatioDiff

#### 含义
**名义上**衡量内部元素的面积分布差异。**实际上**由于实现原因,最终只在数连通域个数(见下方说明)。

#### 算法

```python
num, labels, stats, _ = cv2.connectedComponentsWithStats(mask_bin, connectivity=8)
stats = stats[1:]       # 去掉背景
boxes = [(x, y, w, h, w*h) for x,y,w,h,area in stats if area > 10]
areas = [b[4] for b in boxes]    # 取 w*h(bbox 面积)

area_ratio_diff = |areas_gen.mean()/areas_gen.sum()
                 - areas_gt .mean()/areas_gt .sum()|

score = 100 · exp(-area_ratio_diff / 0.05)
```
任一边无合格连通域 → `MAX_DIFF = 5` → 分数 ≈ 0。

#### ⚠️ 数学等价:等于 `|1/N_gen - 1/N_gt|`

由于 `mean = sum / N`:
```
mean / sum = (sum/N) / sum = 1/N
```
**areas 的具体值完全被消掉**,无论元素大小如何分布,结果只取决于连通域个数:

```
area_ratio_diff ≡ |1/N_gen - 1/N_gt|
```

| N_gt | N_gen | diff | 分数 |
|---|---|---|---|
| 10 | 10 | 0 | 100 |
| 10 | 20 | 0.05 | 36.8 |
| 5 | 10 | 0.1 | 13.5 |
| 1 | 2 | 0.5 | ~0 |
| 100 | 200 | 0.005 | 90.5 |
| any | 0 | 5 | ~0 |

#### 实际性质
- 元素数少时极度敏感(1 vs 2 直接归零)
- 元素数多时几乎不敏感(100 vs 200 还有 90 分)
- 完全不 care 每个元素的实际大小

#### 改进建议
如果希望真的衡量"平均元素大小",应改成:
- `|log(areas_gt.mean() / areas_gen.mean())|`(log 比值)
- 或 `|areas_gt.mean()/(H·W) - areas_gen.mean()/(H·W)|`(按图像面积归一化)
- 或用 Wasserstein 距离比较 area 分布

---

## 5. Legibility

基于 **EasyOCR** 抽取文字,比较文字内容与对比度。

### 5.1 TextJaccard

#### 含义
OCR 识别出的单词集合的 Jaccard 相似度。

#### 算法

```python
txt, _ = easyocr.readtext(img)   # conf >= 0.5 的词
s_gt, s_gen = set(txt_gt.split()), set(txt_gen.split())
jaccard = |s_gt ∩ s_gen| / |s_gt ∪ s_gen|
score = 100 · clip(jaccard, 0, 1)
```

#### 性质
- 完全相同 → 100
- 完全无交集 → 0
- 两图都没文字 → 0/0 走 `+1e-6` 分支 → 分数约 0(可能不合理,两图都无文字其实应该算匹配)

#### 高分条件
生成图里的文字能被 OCR 识别出来,并且和 GT 的词集合尽量一致。

#### 低分情况
- 字形模糊 / 渲染失真导致 OCR 读不出
- 字号太小 / 对比度不足(`conf_thresh=0.5` 过滤掉低置信结果)
- 文字内容本身错了

---

### 5.2 ContrastDiff

#### 含义
整图亮度对比度(近似 WCAG)差异。

#### 算法

```python
gray = 0.299 R + 0.587 G + 0.114 B         # 转灰度到 [0, 1]
min_l, max_l = percentile(gray, [5, 95])   # 5/95 分位去极端噪声
ratio = (max_l + 0.05) / (min_l + 0.05)    # WCAG 近似

diff = clip(|ratio_gt - ratio_gen|, 0, 5)
score = 100 · (1 - diff / 5)               # 线性映射
```

#### 性质
- 用 5/95 分位而不是 min/max,对个别极暗/极亮噪点鲁棒
- 加 0.05 是 WCAG 的防零除常数
- `diff` clip 到 [0, 5],超过 5 直接归零

#### 高分条件
整图的 5/95 分位亮度区间跨度与 GT 接近(整体"明暗反差强度"匹配)。

#### 低分情况
- 生成图整体偏灰(低对比度)vs GT 黑白分明
- 生成图过曝 / 欠曝

---

### 5.3 ContrastLocalDiff

#### 含义
只在 **OCR 检测到的文字区域**内的局部对比度差异。衡量文字本身能不能看清。

#### 算法

```python
for (bbox, text, conf) in ocr_results:
    if conf < 0.5 or bbox_area < 20: continue
    patch = gray[y_min:y_max, x_min:x_max]
    min_l, max_l = percentile(patch, [5, 95])
    contrasts.append((max_l + 0.05) / (min_l + 0.05))

local_contrast = mean(contrasts)          # 所有文字区对比度的均值

if 两图都有文字:   diff = |local_gt - local_gen|
elif 两图都无文字: diff = 0
else:              diff = MAX_DIFF = 5

diff = clip(diff, 0, 5)
score = 100 · (1 - diff / 5)
```

#### 性质
- 只看"能 OCR 到文字的区域",不受 padding 背景干扰
- **一图有字、另一图无字 → 直接满罚**(diff=5,分数=0)

#### 高分条件
GT 和 gen 都有文字,且文字区域背景-前景对比度接近。

#### 低分情况
- 只有 GT 能 OCR 到文字(生成图文字糊了)
- 文字区域虽被检到,但对比度显著不同(比如 GT 黑字白底,gen 灰字白底)

---

## 6. Style

### 6.1 PaletteDistance

#### 含义
两图色相分布的 Earth-Mover's Distance (EMD)。

#### 算法

```python
hue = rgb2hsv(img)[..., 0]          # H 通道 [0, 1]
hist = histogram(hue, bins=36)      # 36-bin 色相直方图,做密度归一化
hist /= hist.sum()

emd = wasserstein_distance(
    np.arange(36), np.arange(36),   # 支撑集:bin 索引
    hist_gt, hist_gen,
)

score = exp(-emd / (36 · 0.08)) ≈ exp(-emd / 2.88)
score = 100 · clip(score, 0, 1)
```

#### 性质
- Wasserstein 距离对直方图的"移动量"敏感,比 L1/L2 更符合人对颜色偏移的感知
- 36 bins 约每 10° 一格(HSV 色相环 360°)
- **不处理色相的环状性质**:红色(接近 1.0)和红色(接近 0.0)会被当成最远

#### 高分条件
整体主色调和 GT 接近(蓝的生成图对蓝的 GT)。

#### 低分情况
整体色调偏移(GT 蓝调,gen 橙调)。

---

### 6.2 Vibrancy

#### 含义
两图**饱和度分布**的 EMD。衡量整体"鲜艳度 / 素净度"是否接近。

#### 算法
与 PaletteDistance 相同,只是换成 HSV 的 S 通道,30 bins:

```python
sat = rgb2hsv(img)[..., 1]
hist = histogram(sat, bins=30)
emd = wasserstein_distance(arange(30), arange(30), hist_gt, hist_gen)
score = 100 · exp(-emd / (30 · 0.05))   # = exp(-emd / 1.5)
```

#### 高分条件
GT 如果是素净灰调,生成图也是素净灰调;GT 如果很鲜艳,生成图也得鲜艳。

#### 低分情况
GT 是灰调 UI 但生成图饱和度拉满(或反之)。

---

### 6.3 PolarityConsistency

#### 含义
衡量两图的**明暗极性**是否一致:是"浅底深字"还是"深底浅字"。同时考虑对比强度。

#### 算法

```python
L = rgb2gray(img)        # [0, 1]
flat = sort(L.ravel())
k = max(1, 0.1 * size)   # 取最暗/最亮各 10% 的均值

bg     = median(flat)        # 背景估计
dark   = mean(flat[:k])      # 最暗 10%
bright = mean(flat[-k:])     # 最亮 10%

# 选离 bg 更远的那端为前景
fg = dark if |bg - dark| >= |bg - bright| else bright

contrast = bg - fg              # 正:深底?不,bg 亮、fg 暗时 contrast>0 → 浅底深字
polarity = sign(contrast)
strength = |contrast|

if str_gt < 1e-6 or str_gen < 1e-6:    # 任一图接近纯色
    return 0.0

pol_score = 1.0 if polarity 相同 else 0.0
mag_diff  = |str_gt - str_gen|

score = pol_score · exp(-mag_diff · 5)
```
最终 ×100 得到 0–100 分。

#### 性质
- **极性反 → 直接 0**(浅底深字 vs 深底浅字,乘 `pol_score=0`)
- **极性一致** → 再按对比强度接近程度打折
- **任一图接近纯色**(strength≈0)→ 直接 0,避免对平坦图给出虚假匹配
- `exp(-mag_diff · 5)` 的衰减:对比强度差 0.2 → `exp(-1)` ≈ 37 分

#### 高分条件
两图同样是"浅底深字"或同样"深底浅字",并且主体与背景的明暗反差强度相近。

#### 低分情况
- 极性颠倒(白底黑字 vs 黑底白字)→ 0
- 生成图渲染成纯色 / 几乎单色 → 0

---

## 7. Perceptual

`compute_perceptual` 直接调用现成库,不做后处理。

### 7.1 SSIM

#### 含义
Structural Similarity Index,传统的像素级结构相似度。

#### 算法

```python
ssim_val = skimage.metrics.structural_similarity(gt, gen, channel_axis=2, data_range=1.0)
score = clip(ssim_val, 0, 1) · 100
```

#### 高分条件
两图像素结构(亮度、对比、局部结构)逐窗口相似 → 分数接近 100。

#### 低分情况
像素对不齐(平移、缩放后 SSIM 会暴跌)、内容失真。

---

### 7.2 LPIPS

#### 含义
Learned Perceptual Image Patch Similarity,基于预训练 VGG 特征的深度感知距离。**越小越像**。

#### 算法

```python
lp = LPIPS(net="vgg")(gt_tensor, gen_tensor).item()
score = clip(lp, 0, 1)     # 注意:直接输出 clip 后的原值!
```

**⚠️ 注意**:`handling_perceptual` 里 `lp` **没有做反向映射**,输出的就是 LPIPS 距离本身(clip 到 [0, 1]),方向与其他指标相反 —— **越小代表越像**。如果要和 SSIM 直接比较,需要用 `1 - lp`。

| LPIPS 值 | 解读 |
|---|---|
| 0.0 | 感知上一致 |
| 0.1 | 非常相似 |
| 0.3 | 明显差异 |
| 0.5+ | 两张图基本是两码事 |

#### 高分条件(距离低)
语义上相似(即使像素不完全对齐,内容/布局接近也可以)。

#### 相对 SSIM
- SSIM 对几何偏移敏感(平移一个像素就跌)
- LPIPS 对几何偏移更鲁棒,对内容/语义差异更敏感

---

## 8. 一览表:scale 严苛度对比

| 指标 | 映射 | scale | 对"差一点"的宽容度 |
|---|---|---|---|
| `geo_score` | exp | 1/3 | 中等 |
| `MarginAsymmetry` | exp | 0.5 | 较宽松 |
| `ContentAspectDiff` | exp | 0.05 | **极严** |
| `AreaRatioDiff` | exp | 0.05 | **极严** |
| `PaletteDistance` | exp | 2.88 | 宽松 |
| `Vibrancy` | exp | 1.5 | 中等 |
| `PolarityConsistency` | exp | 0.2 | 严 |
| `ContrastDiff` | linear | 5 | 中等 |
| `ContrastLocalDiff` | linear | 5 | 中等 |
| `TextJaccard` | clip×100 | - | 严格(OCR 门槛) |
| `SSIM` | clip×100 | - | 严(像素级) |
| `LPIPS` | raw(反向) | - | 越小越好 |

---

## 9. 一图生成想要拿满分需要满足

1. **画布尺寸比例接近 GT**(Geometry)
2. **内容包围盒形状接近 GT**,不被拉扁/拉长(ContentAspectDiff)
3. **四边内容偏移均匀**,无单边跑飞(MarginAsymmetry)
4. **连通域个数接近 GT**(AreaRatioDiff 的实际含义)
5. **OCR 能读出相同的词**(TextJaccard)
6. **整图和文字区的对比度水平接近**(ContrastDiff, ContrastLocalDiff)
7. **色相分布和饱和度分布相近**(PaletteDistance, Vibrancy)
8. **明暗极性一致且强度相近**(PolarityConsistency)
9. **像素/感知空间均对齐**(SSIM, LPIPS)

---

## 10. 已知的设计疑点

在使用这套指标时,需要留意以下几点:

1. **AreaRatioDiff 实际只数连通域个数**(`mean/sum ≡ 1/N`),名字与实现不一致,建议改用 `|log(mean_gt/mean_gen)|`。
2. **LPIPS 输出未反向归一化**,方向与其它 metric 相反,在综合打分时要注意。
3. **PaletteDistance 不处理色相环状性**,红色(0.0)和红色(1.0)会被当最远。
4. **MarginAsymmetry 对"四边同量偏移"给满分**,容易掩盖整体错位问题。
5. **TextJaccard 在两图都无文字时的行为**依赖 `+1e-6` 分母,输出接近 0 而非 1,逻辑上可能不合理。
6. **Legibility 的 EasyOCR 调用**未显式设 GPU,默认会尝试用 CUDA,在无 GPU 环境需要注意。
