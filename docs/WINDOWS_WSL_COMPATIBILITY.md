# Windows / WSL 适配审计

审计日期：2026-08-23  
开发目录：`/home/olm/bigdata`  
生产内核：`/home/olm/bigdata/bigdata/app`

## 1. 当前环境证据

| 项目 | 检测结果 |
|---|---|
| 内核 | `6.18.33.2-microsoft-standard-WSL2` |
| WSL 发行版 | Ubuntu 24.04.2 LTS |
| 架构 | x86-64 |
| Python | 3.12.3 |
| uv | 0.11.7 Linux x86-64 |
| GCC/CMake/Ninja | 已存在 |
| Docker CLI | 已存在 |
| NVIDIA 工具 | 当前 WSL 会话没有 `nvidia-smi` |
| Windows 盘 | C:/D:/E: 以只读 9p/DrvFS 挂载 |
| Windows 可执行文件 | 文件存在，但本会话 WSLInterop 未注册 |
| PowerShell 探针 | 因 WSLInterop/vsock 状态执行失败 |

当前 `bigdata/app/init.sh` 的 CPU 环境检查已在 WSL 内通过：Python 和 8 个依赖版本匹配，
CPU 后端可用，OpenCL 平台数为 0。

结论：**该环境适合开发 Linux 版本和编写 Windows 兼容代码，但当前会话不具备原生
Windows 运行验证条件。Windows 最终证明需要原生 Windows CI runner 或恢复 WSLInterop
后的宿主 PowerShell 测试。**

> **Quintara 状态说明（区别于旧版 `bigdata/app` 审计）**：Quintara 已将入口、路径、
> 锁、GUI 和 doctor 重构为 Python/Qt 跨平台实现，并在仓库 CI 中配置 `windows-latest`
> 测试与 Inno Setup smoke。下文 W-01 至 W-07 描述的是旧比赛目录的阻断项；它们不应被
> 解读为 Quintara 当前源代码仍依赖这些 shell/fcntl 接口。最终 Windows 安装器证据仍以
> `Package smoke` workflow 和真实 Windows 机器结果为准。

## 2. 依赖层可行性

`bigdata/app/uv.lock` 已包含 CPython 3.12 的 Windows x86-64 wheels：

- LightGBM 4.6.0 `py3-none-win_amd64`；
- NumPy 2.3.3 `cp312-win_amd64`；
- pandas 2.3.2 `cp312-win_amd64`；
- SciPy 1.16.2 `cp312-win_amd64`。

因此主要 Python 科学计算依赖具备 Windows 二进制发行物。依赖可获取不等于生产代码已
适配；平台入口、锁、fsync 和系统库检查仍需重构。

## 3. 当前原生 Windows 阻断项

### W-01：只有 POSIX shell 入口

`init.sh`、`train.sh`、`test.sh` 依赖 `/usr/bin/env sh`、shell 环境变量赋值和 `.venv/bin/python`。
Windows 原生命令行需要 Python console entry point 或 PowerShell 启动器。

### W-02：`fcntl` 文件锁

`train.py` 和 `predict.py` 顶层导入 `fcntl` 并调用 `flock`。Python Windows 没有该模块，
当前代码会在导入阶段失败。Quintara 需要平台抽象：POSIX 使用 `fcntl`，Windows 使用
Windows 文件锁实现或成熟的跨平台锁库，同时保留独占、超时和崩溃释放语义。

### W-03：POSIX 权限操作

生产代码多处使用 `os.fchmod(..., 0o644)` 和 `os.chmod`。Windows 权限语义不同，权限设置
应封装成平台能力；原子临时文件、flush、fsync、replace 的数据完整性要求仍然保留。

### W-04：目录 fsync

`artifacts.py` 使用 `os.O_DIRECTORY` 打开目录并 fsync。该接口属于 POSIX 路径。Windows
发布事务需要对应实现，并通过 kill/fault-injection 证明 pointer/result 恢复语义。

### W-05：Linux 系统库检查

`init.sh` 要求：

- `platform.machine() == "x86_64"`；
- `libgomp`；
- Linux OpenCL 动态库习惯；
- Debian bookworm 系统要求文件。

Windows 常返回 `AMD64`，LightGBM wheel 的 OpenMP 动态库布局也不同。doctor 应按平台
使用独立能力检查，不按 Linux 库名判断 Windows 环境。

### W-06：源码闭包绑定 shell 文件

`config.py` 将三个 `.sh` 入口纳入 `SOURCE_PATHS` 哈希。Windows 入口加入后，需要定义
跨平台一致的源码闭包，避免同一模型仅因平台启动包装不同而出现含义不清的校验失败。

### W-07：Windows 构建尚未执行

当前只验证了锁文件包含 Windows wheels。安装、训练、预测、锁恢复、Unicode 路径、长路径、
杀进程恢复和安装器均缺原生 Windows 运行证据。

## 4. 推荐适配方案

### 4.1 平台无关入口

将 shell 文件降为 Linux 薄包装，真正入口统一为 Python console scripts：

- `quintara doctor`
- `quintara train`
- `quintara predict`
- `quintara run`

Windows 使用同一 console script，可额外提供 PowerShell 薄启动器。

### 4.2 平台服务层

建立并测试以下接口：

- `FileLock`：独占锁、非阻塞/超时、进程退出释放；
- `AtomicPublisher`：临时写入、flush、文件 fsync、replace、恢复 journal；
- `RuntimeProbe`：按 Linux/Windows 探测 OS、OpenMP、GPU/OpenCL；
- `ProcessControl`：启动、取消、终止和日志转发；
- `AppPaths`：使用平台标准用户数据、缓存和配置目录。

算法层只依赖这些语义接口，不包含平台判断。

### 4.3 路径和数据

- 全部内部路径使用 `pathlib.Path`；
- 支持空格、中文和非 ASCII 用户名；
- 测试 Windows 长路径；
- 模型、日志和 active 数据写入用户数据目录，而不是安装目录；
- 安装包内 bundled 数据只读；
- 不在 WSL 与 Windows 之间复制虚拟环境。

### 4.4 CPU/GPU

- Windows CPU 作为首个适配目标；
- 原生 Windows LightGBM 最小训练探针通过后再跑生产 fixture；
- GPU 为后续可选矩阵，按实际 OpenCL 设备探测；
- 运行报告记录设备、驱动和依赖；
- CPU 与 GPU 工件分开标识，不以 GPU 可见性自动改变冻结生产配置。

## 5. Windows CI 验收矩阵

建议 GitHub Actions 使用 `windows-latest` 和 `ubuntu-24.04`：

1. `uv sync --frozen`；
2. 导入全部 Quintara 与生产内核模块；
3. doctor CPU 探针；
4. CSV validator 单元/性质测试；
5. 固定小 fixture 训练与预测；
6. Linux/Windows 生产对齐差分测试；
7. 并发锁测试；
8. 发布事务故障注入和恢复；
9. Unicode、空格、长路径；
10. CLI 命令、退出码与结构化输出契约；
11. PySide6/Qt GUI 自动化与高 DPI smoke；
12. 构建安装器，在干净 runner 上安装、启动、升级、卸载。

正式宣称 Windows 支持的最低证据是：原生 Windows runner 完成安装、CPU train、predict、
结果验证和卸载闭环。

## 6. 当前判断

| 问题 | 判断 |
|---|---|
| 能否在当前 WSL 开发 Windows 适配？ | 可以，源码、锁文件和 CI 配置均可在此开发 |
| 主要 Python 依赖是否有 Windows wheel？ | 有 |
| 当前 `bigdata/app` 能否直接在原生 Windows 运行？ | 尚未达到，存在 W-01 至 W-06 |
| 当前 WSL 会话能否代替 Windows 验收？ | 不能，且本会话 WSLInterop 未工作 |
| 推荐的最终验证位置 | GitHub Actions 原生 Windows runner + 一台真实 Windows 10/11 |
