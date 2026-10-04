# Third-party notices / 第三方说明

本文件记录已经随包提供的组件及其来源，不是要求用户另行安装的依赖清单。运行本应用不需要访问以下网站。第三方组件的版权与商标属于各自权利人，许可原文保存在 `licenses/`。

## 随包组件

| 组件 | 版本 | 用途 | 许可原文 |
| --- | --- | --- | --- |
| CPython（Anaconda Windows x64 构建） | 3.12.14 | 私有解释器、标准库与扩展 | `licenses/python/LICENSE`，含标准库相关声明 |
| Qt / PySide6 / Shiboken6 | 6.11.2 | Core、Gui、Widgets、Windows 与图片插件、中文翻译、Python 绑定 | `licenses/Qt/`，按 LGPL v3 选项分发相应库 |
| SQLAlchemy | 2.0.52 | SQLite 数据访问 | `licenses/sqlalchemy/LICENSE`（MIT） |
| greenlet | 3.5.5 | SQLAlchemy 运行支持 | `licenses/greenlet/LICENSE`、`LICENSE.PSF` |
| typing_extensions | 4.16.0 | Python 类型运行支持 | `licenses/typing_extensions/LICENSE`（PSF） |
| SQLite | 3.53.2 | 数据库存储 | `licenses/sqlite/LICENSE.md`（公有领域声明） |
| OpenSSL | 3.5.7 | Python 的哈希与 SSL 标准模块 | `licenses/openssl/LICENSE.txt`（Apache 2.0） |
| bzip2 | 1.0.8 | Python 压缩标准模块 | `licenses/bzip2/LICENSE` |
| liblzma / XZ | 5.8.2 | Python LZMA 压缩标准模块 | `licenses/xz/COPYING`（随包 liblzma 为 0BSD） |
| libffi | 3.4.8 | Python ctypes | `licenses/libffi/LICENSE`（MIT） |
| Expat | 2.8.2 | Python XML 解析 | `licenses/libexpat/COPYING`（MIT） |
| zlib | 1.3.2 | Python ZIP 等压缩功能 | `licenses/libzlib/LICENSE` |
| Microsoft Visual C++ Runtime | 14.44.35208 | Python、Qt 与扩展所需的 MSVC DLL | `licenses/vc14_runtime/LICENSE.RTF`，附方便阅读的 `LICENSE.TXT` |

Qt 内部还使用 HarfBuzz、FreeType、libjpeg、libpng、PCRE2、libwebp 等第三方实现。`licenses/Qt/attributions.json` 保留上游相关模块的名称、版本、版权、许可和源代码地址，`BundledLicenseFiles` 指向该目录内随附的许可文本。部分归属适用于可选构建功能，不能据此推断本包启用了所有功能。

## Qt / PySide6 的源代码与替换

Copyright (C) The Qt Company Ltd. and other contributors.

本包保留可替换的独立 Qt、PySide6 和 Shiboken6 动态库；没有将它们加密、静态嵌入应用或添加禁止调试库修改的限制。适用的 LGPL v3 和 GPL v3 原文位于各组件的 `LICENSES` 目录；商业许可文件是上游原始声明的一部分，本发布包不据此授予商业许可。

对应 **6.11.2** 的完整上游源代码（含构建脚本）可直接获取：

- [PySide6 与 Shiboken6 源代码](https://download.qt.io/official_releases/QtForPython/pyside6/PySide6-6.11.2-src/pyside-setup-everywhere-src-6.11.2.tar.xz)
- [Qt Base 源代码](https://download.qt.io/official_releases/qt/6.11/6.11.2/submodules/qtbase-everywhere-src-6.11.2.tar.xz)
- [Qt Image Formats 源代码](https://download.qt.io/official_releases/qt/6.11/6.11.2/submodules/qtimageformats-everywhere-src-6.11.2.tar.xz)
- [Qt Translations 源代码](https://download.qt.io/official_releases/qt/6.11/6.11.2/submodules/qttranslations-everywhere-src-6.11.2.tar.xz)

构建时下载了上述源代码以保留原始许可与归属。库的二进制内容未修改，仅选取应用使用的组件；对应的 Python 包源码也保留在 `runtime/Lib/site-packages`。没有把开发工具、示例或测试文件加入运行目录。

如需使用自己修改的库：先关闭 RanNovel，将匹配 Windows x64、Python 3.12 / ABI3 和 Qt 6.11 的完整替代库放入 `runtime/Lib/site-packages/PySide6` 与 `shiboken6`，同步更换匹配的 Qt 插件，再通过内置启动器运行。应用 Python 源码可直接修改；没有签名校验阻止替换库。换用不同 ABI 或混用版本可能无法加载。

再次发布时请保留许可、版权与对应源代码获取方式，并保持源码获取地址可用。关于上游许可选项可参阅 [Qt for Python 许可文档](https://doc.qt.io/qtforpython-6/licenses.html)。

## 其他组件来源与打包方式

- [CPython 源代码](https://www.python.org/downloads/source/)；运行文件来自 Python 3.12.14 的 Anaconda Windows x64 构建，保留原始二进制与 PSF 许可。没有包含 Conda 管理器，运行时不访问构建环境。
- [SQLAlchemy](https://github.com/sqlalchemy/sqlalchemy)、[greenlet](https://github.com/python-greenlet/greenlet)、[typing_extensions](https://github.com/python/typing_extensions)：运行文件和版本元数据来自对应版本的已安装发行包。
- 原生支持库来自相同 Python 环境的对应发行包：SQLite、OpenSSL、bzip2、XZ/liblzma、libffi、Expat、zlib、MSVC。只复制运行所需的文件，并保留所附许可。
- Windows 自带的系统 DLL 与系统字体由操作系统提供，本包不复制 Windows 系统文件。所需的 MSVC DLL 在应用目录私有加载，不安装或替换系统运行库。

`runtime/python312.zip` 是从同版本 Python 标准库整理的源码归档；测试、pip、Tk、IDLE、venv 与开发工具不在本应用运行范围内。`python312._pth` 限制模块搜索路径；启动脚本另外限制 DLL 和 Qt 插件搜索路径。目录内无指向原 Conda 环境的符号链接或快捷方式。
