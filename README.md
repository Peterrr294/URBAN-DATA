# URBAN DATA · ARCH 6131 Scale

[在Colab中打开作业笔记本](https://colab.research.google.com/github/Peterrr294/URBAN-DATA/blob/main/Scale/Scale_Plot_Selection.ipynb)

研究范围：Jackson Heights + Corona。以可绘制边界的plot为分析对象；Northern Blvd/BQE仅作参考，不强制筛选结果包含该场地。

## 开始

1. 点击上方Colab链接。此仓库为私有，若Colab要求授权，请登录有访问权限的GitHub账号；若无法打开，可从GitHub下载ipynb并在Colab上传。
2. 在Colab运行设置单元，挂载Drive，创建ARCH6131_Scale目录。
3. 按[数据清单](DATA_SOURCES.md)下载真实数据，放入Drive的data/raw，按笔记本说明统一文件名和字段。
4. 建立boundary.geojson和具有唯一plot_id的plots.geojson；补充人工桥下单元时记录边界来源。
5. 依次关联属性，检查分布与缺失，填写RULES后运行筛选。默认不设置阈值，不伪造筛选结果。
6. outputs包含全部plots、筛选审计、逐层数量、最终GeoJSON、Rhino 3DM和通过GUID关联的CSV。完成至少5套分析数据与>10个Items；当前是框架，不是完成的作业。
7. 修改代码后可在Colab“文件→在GitHub中保存副本”，保存到本仓库；大数据继续存Drive。无需把token写入笔记本。

## 与教师仓库的对应

教师仓库：https://github.com/ivorywang-1005/intro-to-urban-data/tree/main/Scale

|教师教程|本作业|
|---|---|
|S03 GeoPandas Exercise|单独完成基础练习；不要将框架误作S03答案|
|S05 Putting It All Together|读取、投影、逐层筛选、输出|
|S07 Analyzing proximity|plot缓冲区内对象统计|
|S13 Joins and Aggregation|空间关联后汇总为每plot一行|
|S06 Organizing and presenting|3DM + CSV + GUID；替换示例中的邮编/面积排序|
|S09 Calling an API|可选；公开下载足够时不要求注册商业API|

本仓库是独立作业项目，通过教程链接和方法对应连接教师材料，不是fork，不会自动同步。没有修改老师仓库，也没有复制老师答案。教师材料部分旧链接与路径需按本项目实际数据更新。

## 验证状态

发布前检查Notebook JSON及Python代码语法；尚未在Colab运行真实GIS数据，也未完成最终Index/Items排版。
