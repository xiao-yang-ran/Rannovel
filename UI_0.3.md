# RanNovel 0.3：文艺书房界面

本次改造仅涉及 UI，不变更 SQLite 业务表、数据路径或备份逻辑。新版仍由桌面快捷方式通过 novel 环境的 pythonw.exe 无黑框启动。

- 深墨绿侧栏、宣纸色工作区、朱砂主按钮，配色更柔和且保持正文对比度。
- 楷体用于页标题、灵感输入和短句；品牌字形与微软雅黑正文形成清晰层级。
- 山月横幅及六个导航图标均由 Qt 绘制，没有远程图片或运行时网络加载。
- 所有空列表都有首次使用引导；条目出现后提示自动消失。
- 优化输入框、标签、表格、树状大纲、滚动条、选中状态和禁用状态。
- 系统表单按钮使用 PySide6 已内置的 qtbase_zh_CN.qm，无需另外安装翻译包。

系统已提供 KaiTi、Microsoft YaHei UI 等中文字体，因此本次没有下载额外字体或素材。若其他 Windows 设备缺少楷体，Qt 会用可用的中文字体回退，应用仍可离线使用。

预览文件：ui_preview.png 是空库初次打开的状态；ui_filled_preview.png 是临时测试库中的示例灵感；ui_dialog_preview.png 展示战力体系编辑表单。示例数据不会写入正式数据库。验证命令：

    conda activate novel
    python -m unittest discover -s tests_v2 -v
    python -m unittest discover -s tests -v
