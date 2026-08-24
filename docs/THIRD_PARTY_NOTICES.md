# Third-party notices

Quintara 运行时使用或兼容以下组件。发布候选的 `dist/sbom.json` 会记录安装环境中
可发现的版本、许可证元数据和主页；二进制分发应同时保留本文件和上游许可证全文。

| 组件 | 作用 | 许可证/条款入口 |
| --- | --- | --- |
| Python | 解释器（源码发行） | [PSF License](https://docs.python.org/3/license.html) |
| NumPy / pandas / SciPy | 数值与表格计算 | 各自 BSD-3-Clause notice |
| LightGBM | 排序/回归模型 | [LightGBM MIT license](https://github.com/lightgbm-org/LightGBM/blob/master/LICENSE) |
| PySide6 / Qt | 独立桌面 GUI | [Qt licensing](https://www.qt.io/licensing/)；发布包按 LGPL/GPL 条款随附 notice |
| BaoStock Python connector | 用户主动更新行情与额外特征 | [BaoStock project](https://github.com/zxygithub/baostock) 与 [服务条款](https://www.baostock.com/) |
| PyInstaller | Python-free 打包链（发布工具） | [PyInstaller license](https://github.com/pyinstaller/pyinstaller/blob/develop/COPYING.txt) |
| Inno Setup | Windows 安装器（发布工具） | [Inno Setup license](https://jrsoftware.org/files/is/license.txt) |
| Hypothesis / pytest / Ruff / ty | 开发与验证依赖 | 仅开发环境使用，各自上游 notice |

发布包包含项目自有的训练与排序组件。组件版本、来源摘要和修改记录随每次发布的
SBOM 与源代码一同保存，用户可据此核对安装包内容和许可证范围。
