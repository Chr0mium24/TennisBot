# Baseline 对落点预测误差的影响分析 - 2026-07-13

## 1. 误差从哪里来

本次分析只讨论视觉测量误差对落点预测的影响。真实接球闭环还需要同步双目轨迹、真实落点 ground truth、ROS/Gazebo 后端链路和底盘控制验证；这些不在本文结论范围内。

落点误差主要来自四部分：

1. YOLO 框中心偏移。

   YOLO 检测框中心不一定等于人工 bbox 中心。双目三角化主要使用左右图的 x 坐标差，也就是视差，所以 x 方向偏移会直接变成深度误差。

2. 双目标定和校正残差。

   标定的重投影误差、极线误差和校正后 y 方向残差会进入三角化结果。本文把 stereo RMS 作为额外的像素级几何残差纳入计算。

3. baseline 和距离导致的深度放大。

   双目深度公式是：

   ```text
   Z = f * B / d
   ```

   深度误差近似是：

   ```text
   depth_error ≈ Z^2 / (f * B) * disparity_error
   ```

   所以在其他条件固定时，误差随距离 `Z` 的平方增长，随 baseline `B` 增大而下降。

4. 高度误差会影响落地时间。

   如果球的高度估计有误差，预测到地面的时间会变化，水平落点也会跟着变化。本文用一个固定弹道读数把高度误差换算为水平落点误差。

本文后续把除 `Z` 和 `B` 以外的变量全部固定。最终结果只看两个变量：

- `Z`: 球到相机的距离；
- `B`: 双目 baseline。

## 2. 固定输入：标定数据

使用当前数据最多且硬件验证通过的标定包：

- `artifacts/calibration/cam1`
- `artifacts/calibration/cam2`
- `artifacts/calibration/stereo_cam1_cam2`

原始标定数据如下：

| 项目 | 数值 |
|---|---:|
| cam1 有效标定图 | 53 / 53 |
| cam1 RMS | 0.1777 px |
| cam1 `new_camera_matrix.fx` | 436.299 px |
| cam2 有效标定图 | 50 / 50 |
| cam2 RMS | 0.1801 px |
| cam2 `new_camera_matrix.fx` | 408.324 px |
| stereo 有效 pair | 38 / 38 |
| stereo RMS | 0.2121 px |
| epipolar RMS | 0.2568 px |
| rectification y p95 | 0.4296 px |
| 当前实测 baseline | 0.164989 m |

当前标定分辨率是 `1280x720`，YOLO 数据集图像是 `3840x2160`。本文按同一视场和同一裁切假设，把焦距缩放到 4K 坐标：

```text
f_720 = (436.299 + 408.324) / 2 = 422.311 px
f_4k = 422.311 * 3 = 1266.934 px
```

stereo RMS 也按 3 倍缩放：

```text
stereo_rms_4k = 0.2121 * 3 = 0.636 px
```

后续如果使用最终 4K 模式重新标定，应直接替换这里的 `f_4k` 和 stereo RMS。

## 3. 固定输入：YOLO 中心偏移数据

YOLO 偏移评测使用：

- dataset split: `tools/yolo/workspace/runs/combined_current_fixed_cloudy_20260707/val.txt`
- 图像分辨率: `3840x2160`
- model: `artifacts/models/tennis_ball_yolo/model.pt`
- inference size: `1280`
- confidence threshold: `0.05`
- 只统计 `IoU >= 0.5` 的准确匹配框；
- 不统计漏检、错检、明显偏移框。

这个口径回答的是：球已经被 YOLO 正确框住时，框中心还有多少偏移。

原始统计如下：

| 项目 | 数值 |
|---|---:|
| val images | 975 |
| positive images | 792 |
| GT boxes | 792 |
| predicted boxes | 546 |
| accurate matched boxes, IoU >= 0.5 | 377 |

准确匹配框的中心偏移：

| 指标 | p50 | p95 |
|---|---:|---:|
| center error | 1.431 px | 5.673 px |
| abs dx | 0.759 px | 3.606 px |
| abs dy | 0.889 px | 4.243 px |

第一张图把所有准确匹配框对齐到人工 bbox 中心后叠在一起。绿色是人工 bbox，红色是 YOLO bbox，黄色是 YOLO 中心偏移。

![YOLO 框叠加图](assets/baseline_yolo_overlay_clean_20260713.jpg)

第二张图是中心偏移 `E = sqrt(dx^2 + dy^2)` 的分布。

![YOLO 中心偏移直方图](assets/baseline_yolo_center_hist_clean_20260713.jpg)

第三张图单独展示 `abs(dx)` 和 `abs(dy)`。后续三角化主要使用 x 方向误差。

![YOLO 轴向偏移直方图](assets/baseline_yolo_dxdy_hist_clean_20260713.jpg)

## 4. 从 YOLO 偏移得到视差误差

左右相机如果有相同量级的 x 方向中心偏移，视差误差按平方和合成：

```text
disparity_error_yolo = sqrt(2) * abs_dx
```

再叠加 4K 坐标下的 stereo RMS：

```text
disparity_error = sqrt(disparity_error_yolo^2 + stereo_rms_4k^2)
```

代入当前实测数据：

| 场景 | abs dx | YOLO 视差误差 | 合成视差误差 |
|---|---:|---:|---:|
| p50 | 0.759 px | 1.073 px | 1.247 px |
| p95 | 3.606 px | 5.100 px | 5.139 px |

后续用这两个场景做结果表：

- p50：代表已经准确检测到时的中位数误差；
- p95：代表已经准确检测到时的尾部误差。

## 5. 落点误差计算模型

本文把落点误差拆成三项：

```text
landing_error = sqrt(depth_error^2 + lateral_error^2 + height_landing_error^2)
```

### 5.1 深度误差

```text
depth_error = Z^2 / (f * B) * disparity_error
```

这是主导项。它同时受距离 `Z` 和 baseline `B` 影响。

### 5.2 横向误差

横向误差由图像 x 方向中心误差投影到空间：

```text
lateral_error ≈ Z / f * (abs_dx / sqrt(2))
```

这一项随距离线性增长，不直接受 baseline 影响。

### 5.3 高度带来的落点误差

高度误差先换算为空间高度误差：

```text
height_error ≈ Z / f * (abs_dy / sqrt(2))
```

再通过落地时间换算到水平落点：

```text
height_landing_error ≈ 1.68 * height_error
```

这里固定使用一个代表性弹道读数：

| 参数 | 固定值 |
|---|---:|
| 球高度 | 1.0 m |
| 水平速度 | 10 m/s |
| 竖直速度 | -4 m/s |
| 重力加速度 | 9.81 m/s² |

在当前数据下，深度误差远大于横向项和高度项。保留这两项是为了不忽略高度影响，但最终结论主要由深度误差决定。

## 6. 固定所有输入后，误差只与距离和 baseline 有关

把当前实测数据和固定假设代入后，p50 场景可以写成：

```text
E_p50(Z, B) =
sqrt(
  (0.0009846 * Z^2 / B)^2
  + (0.0004234 * Z)^2
  + (0.0008315 * Z)^2
)
```

p95 场景可以写成：

```text
E_p95(Z, B) =
sqrt(
  (0.0040565 * Z^2 / B)^2
  + (0.0020126 * Z)^2
  + (0.0039682 * Z)^2
)
```

其中：

- `E`: 落点误差预算，单位 m；
- `Z`: 球到相机距离，单位 m；
- `B`: baseline，单位 m。

到这里为止，除了 `Z` 和 `B`，其他变量都已经被当前实测数据或固定假设吸收进系数。

## 7. 只改变 baseline 的结果

本文比较三种 baseline：

| 方案 | baseline |
|---|---:|
| 当前实测 | 0.164989 m |
| 方案 A | 0.250000 m |
| 方案 B | 0.300000 m |

baseline 增大时，深度误差近似按 `1 / B` 下降：

| baseline 变化 | 误差比例 | 误差下降 |
|---|---:|---:|
| 16.5cm -> 25cm | 0.660x | 34.0% |
| 16.5cm -> 30cm | 0.550x | 45.0% |
| 25cm -> 30cm | 0.833x | 16.7% |

### 7.1 p50 结果

单位是 m。

| baseline | 5m | 10m | 15m | 20m | 23.77m |
|---|---:|---:|---:|---:|---:|
| 16.5cm | 0.15 | 0.60 | 1.34 | 2.39 | 3.37 |
| 25cm | 0.10 | 0.39 | 0.89 | 1.58 | 2.23 |
| 30cm | 0.08 | 0.33 | 0.74 | 1.31 | 1.85 |

这张图对应 p50 结果。距离变远后，误差增长明显加快；30cm 始终优于 25cm，但差距是固定比例，不是数量级变化。

![p50 落点误差曲线](assets/baseline_landing_error_p50_curve_clean_20260713.jpg)

### 7.2 p95 结果

单位是 m。

| baseline | 5m | 10m | 15m | 20m | 23.77m |
|---|---:|---:|---:|---:|---:|
| 16.5cm | 0.62 | 2.46 | 5.53 | 9.84 | 13.89 |
| 25cm | 0.41 | 1.62 | 3.65 | 6.49 | 9.17 |
| 30cm | 0.34 | 1.35 | 3.04 | 5.41 | 7.64 |

这张图对应 p95 结果。p95 使用的是成功检测样本中的较大偏移，因此远场误差明显更大。

![p95 落点误差曲线](assets/baseline_landing_error_p95_curve_clean_20260713.jpg)

## 8. 按误差目标反推可用距离

如果反过来看“误差要控制在某个目标以内，最多能看到多远”，结果如下。

### 8.1 p50 场景

单位是 m。

| 误差目标 | 16.5cm | 25cm | 30cm |
|---|---:|---:|---:|
| <= 0.10m | 4.1 | 5.0 | 5.5 |
| <= 0.30m | 7.1 | 8.7 | 9.6 |
| <= 0.50m | 9.2 | 11.3 | 12.3 |
| <= 1.00m | 12.9 | 15.9 | 17.5 |

### 8.2 p95 场景

单位是 m。

| 误差目标 | 16.5cm | 25cm | 30cm |
|---|---:|---:|---:|
| <= 0.10m | 2.0 | 2.5 | 2.7 |
| <= 0.30m | 3.5 | 4.3 | 4.7 |
| <= 0.50m | 4.5 | 5.6 | 6.1 |
| <= 1.00m | 6.4 | 7.9 | 8.6 |

下图把 p50 和 p95 都画在一起。实线是 p50，虚线是 p95，颜色区分 baseline。

![误差目标可达距离曲线](assets/baseline_distance_limit_clean_20260713.jpg)

## 9. 结论

1. baseline 从 25cm 增加到 30cm 有收益，但收益有限。

   在其他条件不变时，30cm 相比 25cm 的深度误差约为 `25 / 30 = 83.3%`，也就是下降约 `16.7%`。

2. 当前主要瓶颈是远距离视差误差。

   当前成功检测样本里，`abs_dx p50 = 0.759px`。左右相机合成并叠加标定残差后，p50 视差误差约 `1.247px`。这个像素级误差在远距离会被 `Z^2 / (f * B)` 放大。

3. 30cm baseline 在 10m 以内更有实用意义，远场仍然压力很大。

   用当前数据估计，30cm baseline 在 10m 处 p50 误差约 `0.33m`，p95 误差约 `1.35m`。到 20m 时，p50 已约 `1.31m`，p95 已约 `5.41m`。

4. 如果目标是标准球场远端稳定接球，只增加 baseline 不够。

   后续更关键的是降低 YOLO x 方向中心偏移、提高有效焦距或降低 FOV、做最终 4K 双目标定，并用真实同步双目轨迹验证落点。

## 10. 后续需要补的数据

要把本文从误差预算升级为真实落点验证，还需要：

- 最终 25cm / 30cm 机械安装后的双目标定包；
- 4K 原始分辨率下的 `camera_matrix` / `new_camera_matrix` / stereo rectification；
- 同步双目视频，包含真实飞行轨迹；
- 每条轨迹的真实落点 ground truth；
- 相机到球场坐标系的外参；
- 每帧 camera timestamp / ROS timestamp；
- 轨迹拟合输出的 predicted landing point；
- predicted landing point 与 ground truth landing point 的 p50 / p90 / p95 / max 误差。
