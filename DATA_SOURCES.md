# 数据来源与输入清单

这是下载清单，不代表数据已经下载或核实覆盖。下载后记录数据版本、实际获取日期、原始文件名、CRS、字段和处理步骤。API需分页，不能把首批返回当作完整数据。

|文件/角色|数据|官方入口|格式|限制|
|---|---|---|---|---|
|plots|MapPLUTO|https://www.nyc.gov/content/planning/pages/resources/datasets/mappluto-pluto-change|SHP ZIP → GeoJSON|候选地块几何与属性；桥下空间另画边界|
|boundary|2020 NTAs|https://data.cityofnewyork.us/City-Government/2020-Neighborhood-Tabulation-Areas-NTAs-/9nt8-h7nd|GeoJSON|选择并记录Jackson Heights、Corona对应单元；不是以社区均值代替plot|
|buildings|Building footprints|https://data.cityofnewyork.us/City-Government/BUILDING/5zhs-2jue|GeoJSON/SHP|建筑几何用于后续覆盖分析；不等于可开发面积|
|crashes|NYPD crashes|https://data.cityofnewyork.us/d/h9gi-nx95|GeoJSON/CSV|Queens，2021–2025；坐标缺失单独记录|
|traffic|DOT traffic counts|https://data.cityofnewyork.us/Transportation/Automated-Traffic-Volume-Counts/7ym2-wayt|CSV，解析WktGeom|Vol是15分钟计数；先按测站日期方向聚合，不能简单数记录|
|food_stores|Retail food stores|https://data.ny.gov/Economic-Development/Retail-Food-Stores/9a8c-vfzj|GeoJSON/CSV|核对地理编码；未必能直接识别鱼店|
|tracts|2020 census tracts|https://data.cityofnewyork.us/City-Government/2020-Census-Tracts/63ge-mke6|GeoJSON|GEOID保持字符串，11位|
|age|ACS 2024 five-year|https://www.census.gov/data/developers/data-sets/acs-5year.html|JSON/CSV + tract join|B01001年龄；B08201车辆；保留MOE；2020–2024估计|
|health|CDC PLACES|https://www.cdc.gov/places/tools/data-portal.html|CSV + tract join|成人模型估计，核对发布年、指标年与地理版本；非地块实测|

目录建议：Google Drive/ARCH6131_Scale/data/raw。大体积数据放Drive，仓库保存代码、来源和精简成果。先核对各源使用条款。年龄健康关联以GEOID为键；原始统计尺度不随导出GeoJSON而改变。
