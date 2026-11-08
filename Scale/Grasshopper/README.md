# 从 Colab 到 Grasshopper

## 1. 导出数据

在自己的 Colab 最下方新增代码格，粘贴 `01_export_from_colab.py` 全部内容并运行。它读取 Drive 里已保存的分析成果，复用分步图纸的五层条件，裁切地块显示轮廓，输出 `gh_plot_atlas.json` 和 `candidate_items.csv`。在 Drive 的 `ARCH6131_Scale/outputs` 找到最新 `Grasshopper_Export_*.zip`，下载并解压。Colab 未运行时，JSON 与 CSV 尚未生成。

## 2. 建立 Grasshopper 组件

在 Rhino 8 中打开 Grasshopper，放置 **Python 3 Script** 组件并保持 Script-Mode。将 `02_grasshopper_component.py` 的全部内容粘贴到编辑器。组件使用 Rhino 自带的 RhinoCommon。把 `x` 和 `y` 保留为 Item Access，并设置为 String。给 `x` 接一个 Panel，填入本地解压目录下 `gh_plot_atlas.json` 的完整路径。初次运行时 `y` 可留空。

把默认 `a` 输出改名为 `Base`。放大组件，按顺序加其余输出，名称区分大小写。保留默认的 `out` 以查看错误。

| 输出 | 内容 |
|---|---|
| Base | 边界及裁切后的全部地块轮廓 |
| Sites | 入选地块的原位轮廓 |
| Cards | 排列后的地块轮廓副本 |
| Links | 原位到卡片的连接线 |
| LabelPoints | 卡片的文字位置 |
| Labels | 编号、地块 ID、用途及各指标 |
| Theme | `y` 指定的专题图几何 |
| Colors | 与 Theme 等长的颜色列表 |
| TrafficLabels | 交通点的方向、车流与观测天数 |
| Info | 导入数量、范围和卡片缩放比例 |

右键可给 `LabelPoints` 和 `Labels` 各自 Extract Parameter。将两组输出接到 **Text Tag 3D** 的 Location 与 Text 端口，给 Size 接滑块。在 Rhino 视窗切到 Top 并 Zoom Extents。用 **Custom Preview** 分别给 Base、Sites、Cards、Links 配色，专题图将 Theme 接 Geometry，Colors 接 Material。设置自定义预览后，可关闭 Python 组件自身的预览以免重复。

## 3. 调整卡片与专题图

默认卡片放在地图上方，按同一缩放比例绘制。可选添加 Item Access 的数字输入 `Cols`、`CardWidth`、`CardHeight`、`Gap` 并接滑块。距离输入均以英尺计。先在 Rhino 将模型单位设置成英尺。

`y` 可填写 `building`、`food`、`crashes`、`pedestrian`、`age`、`asthma` 或 `traffic`。年龄和健康用统计区轮廓。交通用实测位置和方向数据，重合位置的圆可以重叠。颜色按当前图层的数值范围映射，范围见 Info。Base、Cards 和 Links 可分别烘焙至 Rhino 图层。

`origin_xy` 记录平移前的 EPSG:2263 原点。导出保留多部件和内环作为独立闭合曲线。最终卡片数以本次 Drive 数据及筛选结果为准。当前 Rhino 8 的组装步骤和文件需在本机运行验证。
