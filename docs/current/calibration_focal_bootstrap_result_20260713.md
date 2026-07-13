# 焦距不确定性 bootstrap 结果 - 2026-07-13

## 1. 目的

深度误差公式中除了视差误差 `σd`，还可以传播焦距不确定性 `σf`：

$$
\frac{\sigma Z}{Z}
\approx
\sqrt{
\left(\frac{\sigma f}{f}\right)^2
+ \left(\frac{\sigma B}{B}\right)^2
+ \left(\frac{\sigma d}{d}\right)^2
}
$$

标定 RMS 不能直接当作 `σf`。RMS 是重投影残差，反映整体几何拟合误差；`σf` 是焦距参数本身的不确定性。本文用 bootstrap 从现有标定图组估计 `σf`。

## 2. 方法

对 cam1 和 cam2 分别执行：

```text
每次从原始标定视图中有放回抽样，抽样数量等于原视图数量
-> 重新执行 OpenCV mono calibration
-> 重新计算 new_camera_matrix
-> 记录 new_fx / new_fy
-> 重复 500 次
```

本文后续深度误差使用的是 `new_camera_matrix.fx` 口径，因此 bootstrap 也统计 `new_fx`。

## 3. 单相机结果

| 相机 | 视图数 | 成功迭代 | full new_fx | bootstrap new_fx std | new_fx p05 | new_fx p50 | new_fx p95 |
|---|---:|---:|---:|---:|---:|---:|---:|
| cam1 | 53 | 500 / 500 | 436.299 px | 6.550 px | 430.661 px | 436.438 px | 439.466 px |
| cam2 | 50 | 500 / 500 | 408.324 px | 41.612 px | 386.574 px | 430.194 px | 469.106 px |

cam2 的 `new_fx` bootstrap 分布明显更宽。这里没有再用标定 RMS 反推 `σf`，而是直接使用重采样得到的 `new_fx` 标准差。

## 4. 合成 4K 焦距不确定性

深度分析中使用的 720p 平均焦距是：

$$
\begin{aligned}
f_{720}
&= \frac{new\_fx_{cam1} + new\_fx_{cam2}}{2} \\
&= \frac{436.299 + 408.324}{2} \\
&= 422.311 \text{ px}
\end{aligned}
$$

两个相机的 `new_fx` bootstrap 标准差分别是：

$$
\sigma fx_{cam1} = 6.550 \text{ px}
$$

$$
\sigma fx_{cam2} = 41.612 \text{ px}
$$

平均焦距的不确定性按独立项平方和合成：

$$
\begin{aligned}
\sigma f_{720}
&= \frac{\sqrt{\sigma fx_{cam1}^2 + \sigma fx_{cam2}^2}}{2} \\
&= \frac{\sqrt{6.550^2 + 41.612^2}}{2} \\
&= 21.062 \text{ px}
\end{aligned}
$$

缩放到 4K 坐标：

$$
\begin{aligned}
f_{4k}
&= 422.311 \cdot 3 \\
&= 1266.934 \text{ px}
\end{aligned}
$$

$$
\begin{aligned}
\sigma f_{4k}
&= 21.062 \cdot 3 \\
&= 63.187 \text{ px}
\end{aligned}
$$

相对焦距不确定性：

$$
\begin{aligned}
\frac{\sigma f}{f}
&= \frac{63.187}{1266.934} \\
&= 0.0499 \\
&= 4.99\%
\end{aligned}
$$

## 5. 后续深度误差采用值

后续 baseline 深度误差分析采用：

$$
f = 1266.934 \text{ px}
$$

$$
\sigma f = 63.187 \text{ px}
$$

$$
\frac{\sigma f}{f} = 4.99\%
$$
