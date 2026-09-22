# RanNovel 0.2：世界观与地理拆分

由于旧代码目录带有上一沙箱账户留下的 Windows 写入锁定，本次升级使用 `app_v2/` 扩展层复用原有功能，不复制业务数据，也不修改旧表。

## 新入口

```powershell
conda activate novel
pythonw C:\RanNovel\RanNovel.pyw
```

`app_v2` 导入原 `app` 中的灵感、时间线、人物、大纲、数据库和备份模块，并新增：

- `world_settings`：独立世界观设定表。
- `WorldbuildingPage`：世界总纲、战力体系、能量与魔法、种族、文明、政治、宗教、经济、历史、文化、语言等分类设定。
- `GeographyPage`：只记录具有空间位置的区域、国家、城市、地貌、建筑、遗迹和路线。
- 世界观全字段检索、分类筛选、设计提示和自定义字段。
- 地理条目的全文搜索和地理类型筛选。

原有地点继续保存在 `world_locations`，不会迁移或删除；新世界观内容保存在 `world_settings`。

## 测试

```powershell
conda activate novel
python -m unittest discover -s tests_v2 -v
```
