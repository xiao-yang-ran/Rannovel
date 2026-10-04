# RanNovel 1.1.0 · Windows 便携版

RanNovel 是完全离线的桌面写作应用，支持长篇、随笔和片段，提供富文本编辑、人物关系、世界观设定、故事时间线、灵感管理及整库备份恢复。应用不使用云服务、在线素材或遥测。

**下载整个文件夹，完整解压，双击 `Start_RanNovel.cmd` 即可运行。** Python、Qt 和所需第三方库已内置，无需安装 Python、Conda、Qt、pip 包或 Visual C++ 运行库，也无需联网。

## 环境要求

- Windows 10 1809 或更高版本、Windows 11，**x64（Intel / AMD 64 位）**。本包不适用于 32 位 Windows、原生 ARM64、macOS 或 Linux。Qt 的系统支持范围见 [Qt 6.11 官方说明](https://doc.qt.io/qt-6.11/windows.html)。
- 将文件夹放在当前用户可写的位置，例如 `D:\Apps\RanNovel`；不要直接在压缩包内运行，也不要放到需要管理员权限的系统目录。
- 程序文件约 73 MiB。建议至少预留 200 MiB，并为作品图片和备份另留空间。
- 支持中文和空格路径。字体使用 Windows 本机字体，无需下载字体。

## 安装与运行

1. 从 GitHub 的 **Code → Download ZIP** 下载完整项目，或克隆仓库；只下载 `main.py` 无法运行。
2. 将全部内容解压到一个可写文件夹，保留 `app`、`runtime`、`resources` 等目录的相对位置。
3. 双击 **`Start_RanNovel.cmd`**。首次启动会自动建立 `userdata` 资料目录。
4. 在“作品 → 新建作品…”中选择写作模式。长篇需先创建分卷和章节，再开始写作。

启动器使用 `runtime/pythonw.exe`，不依赖文件关联或电脑里已有的 Python。它仅设置当前进程的 DLL 与 Qt 搜索路径，不安装服务、不修改系统 PATH、注册表或 Python 环境。每个资料目录只允许一个实例运行。

需要查看启动诊断时，在项目文件夹内打开 PowerShell：

```powershell
.\runtime\python.exe -I -B -X utf8 .\main.py
```

不要执行 `pip install`，不要单独移动或升级某个 Qt DLL。更新程序时先备份，关闭窗口，再替换完整的程序文件，保留自己的 `userdata`。卸载只需关闭程序并删除文件夹；删除前请取走创作资料和备份。

## 目录结构

```text
RanNovel/
├── Start_RanNovel.cmd          # 双击启动入口，使用相对路径
├── main.py                    # 私有运行时初始化及启动错误提示
├── README.md                  # 本说明
├── THIRD_PARTY_NOTICES.md      # 第三方版本、许可、来源及替换说明
├── .gitignore                 # 排除个人资料、日志与缓存
├── .gitattributes             # 文本换行与二进制文件规则
├── app/                       # 完整的 RanNovel Python 源码
│   ├── config.py              # 便携资料路径
│   ├── database.py            # SQLite 初始化与结构迁移
│   ├── domain.py / models.py  # 业务规则及数据模型
│   ├── services/              # 资料操作、完整性校验、备份恢复
│   └── ui/                    # 界面、正文、图片、关系图等模块
├── resources/
│   └── RanNovel.ico           # 程序图标
├── runtime/                   # 可直接使用的 Windows x64 私有运行时
│   ├── python.exe / pythonw.exe
│   ├── python312.dll / python3.dll
│   ├── python312._pth         # 隔离系统与用户的 Python 搜索路径
│   ├── python312.zip          # 必需的 Python 标准库，不是历史发布包
│   ├── *.dll / *.pyd          # SQLite、压缩、加密、MSVC 等运行文件
│   └── Lib/site-packages/
│       ├── PySide6/           # Qt Core、Gui、Widgets、插件与中文翻译
│       ├── shiboken6/         # Qt Python 绑定运行支持
│       ├── sqlalchemy/        # 数据库访问库
│       ├── greenlet/          # SQLAlchemy 所需支持
│       └── typing_extensions.py
├── licenses/                  # 第三方许可原文与 Qt 版权归属
└── userdata/                  # 运行后生成，不随发布包提供，不上传 GitHub
    ├── rannovel.db            # 作品、正文与资料数据库
    ├── assets/                # 正文和图库图片
    ├── backups/               # 默认备份目录
    └── startup-error.log      # 仅启动发生异常时生成
```

界面由 `app/ui` 中的 Python 代码创建，没有额外的 `.ui` 或 `.qrc` 文件。Qt 的 Windows 平台插件、GIF/JPEG/ICO/WebP 图片插件和 `qtbase_zh_CN.qm` 中文翻译已内置；PNG、BMP 等由 Qt Gui 提供。

`runtime` 是本应用的运行环境，省去了 pip、Conda、开发工具、测试套件及未使用的 Qt 模块；不作为通用 Python 开发环境使用。项目自己的源码可直接编辑，运行时无需重新构建界面资源。

## 创作功能

- 长篇拥有独立的分卷、分章、地点、设定和时间线。随笔与片段各有一篇正文，人物库和人物关系全局共享。
- 富文本正文支持 800 毫秒防抖自动保存、字数统计、查找替换及图片插入。切换章节、作品、页面和退出前会尝试保存；保存失败时保留当前输入。
- 图片可通过按钮、拖放或剪贴板导入。支持 PNG、JPEG、BMP、GIF、WebP；单张上限 50 MiB、4000 万像素。外部 HTML 中的图片需单独导入。
- 作品和关联资料支持搜索、分页；同名作品以编号区分。关系图最多显示 200 人，可缩小搜索范围。
- 人物、地点和灵感支持多张配图。重复图片复用存储，解除引用后回收无用图片；编辑器撤销仍需使用的图片暂时保留。
- 灵感可关联作品和正文。“解除正文关联”保留作品归属；“文件 → 已使用灵感…”中的“放回待用池”同时解除二者。
- 配图管理立即保存，取消文字表单不会撤销已经执行的配图变更。

## 数据、备份与旧版迁移

所有创作资料保存在**本程序文件夹内的 `userdata`**。移动整个文件夹即可携带程序和资料；不要在程序运行时移动文件夹或直接复制正在写入的数据库。移动或升级前建议先使用“文件 → 立即备份…”。

“立即备份”生成包含数据库与被使用图片的 ZIP，并校验哈希及关联完整性。“从 ZIP 恢复…”接受格式版本 2、数据库版本 2 的整库备份，恢复会替换当前资料，因此请先确认要恢复的文件。恢复前自动保留安全备份，失败则回退。

如果当前图片损坏导致无法正常备份，恢复流程会先保存 `recovery_before_restore_*.zip` 原始资料包；这种原始包供人工取回文件，不能直接通过恢复菜单导入。备份和安全快照会一直保留，请自行管理占用空间。

旧版数据通常在 `%APPDATA%\RanNovel`。本便携版不会自动读取、迁移或改写该目录：

1. 在旧版中创建兼容的整库备份并关闭旧版。
2. 启动本便携版，选择“文件 → 从 ZIP 恢复…”，导入该备份。
3. 核对正文和图片后再决定如何保留旧资料。

旧格式备份需使用对应旧版处理。如果程序目录的 `data/rannovel.db` 中存在旧资料，程序仍会停止启动并提示人工核实，避免静默忽略旧数据。

## 上传 GitHub

当前文件夹就是仓库根目录。可使用 Git 或 GitHub Desktop 将其中的源代码、`runtime`、`resources`、`licenses` 和说明文档一起上传。运行依赖已全部落地，无需 Git LFS、子模块或下载依赖的安装脚本。

单个文件均小于 25 MiB，也低于 GitHub 普通 Git 的 100 MiB 限制；文件数量较多，建议使用 Git 或 GitHub Desktop 上传。[GitHub 文件大小说明](https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-large-files-on-github)

`.gitignore` 已排除 `userdata`、数据库、备份目录、日志及缓存。**浏览器手工上传不应用 `.gitignore`，请不要选中运行后生成的 `userdata`。** `runtime/python312.zip` 是标准库，必须上传。已有本地 `.git` 提交历史保留；不是另一个发布包。

## 本版改进与验证

1.1.0 包含备份原子写入与完整性验证、恢复失败回退、图片去重与回收、数据库事务迁移、单实例保护、搜索分页、表单失败保留输入及后台备份恢复。便携版进一步整合 Python/Qt/数据库依赖，改用相对启动路径与程序内资料目录。

本次发布验证包括：隔离系统 Python 环境、检查全部原生 DLL 依赖、中文和空格路径迁移、完整启动入口、页面初始化、正文保存、图片导入与备份恢复。验证使用临时资料，交付前全部移除。已在当前 Windows x64 主机验证；未在独立的全新 Windows 虚拟机上测试字体、输入法和不同显示缩放。

第三方版权、许可文本、精确版本与对应源代码获取地址见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。
