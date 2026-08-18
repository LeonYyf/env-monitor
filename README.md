# 环境监测数据分析系统

洁净车间环境监测数据分析桌面程序：把 Excel 环境监测数据导入数据库，经过清洗、分析，自动生成合规性判定与业务解读报告。

## 功能流程

1. **数据导入** — 读取 Excel（尘埃粒子、风量两个表）
2. **数据清洗** — 缺失值 / 异常值 / 时间格式 / 去重
3. **探索分析** — 统计描述 + 可视化图表
4. **结果报告** — 尘埃粒子合规性判定、房间体积一致性检查、自动业务解读、导出 Excel

## 环境要求

- **Python 3.11 或 3.12**（推荐，最稳定）
- 操作系统：Windows / macOS 均可

## 安装步骤

### 1. 安装 Python

**Windows：**

1. 打开 <https://www.python.org/downloads/>，下载 Python 3.11 或 3.12 的安装包
2. 双击运行安装器，**务必勾选 "Add Python to PATH"**（在安装窗口底部）
3. 一路下一步完成安装

**macOS：**

```bash
brew install python@3.12
```

或者同样去 python.org 下载安装包。

### 2. 安装依赖库

打开终端（Windows 用「命令提示符」或 PowerShell），进入本项目文件夹，执行：

```bash
pip install -r requirements.txt
```

> 如果提示 `pip` 找不到，改用 `python -m pip install -r requirements.txt`。

### 3. 运行程序

在本项目文件夹内执行：

```bash
python main.py
```

数据库会自动创建，无需额外配置。

## 使用说明

1. 进入「数据导入」，选择 Excel 文件，预览并导入
2. 进入「数据清洗」，按向导完成清洗
3. 进入「探索分析」，查看统计与图表
4. 进入「结果报告」，选择洁净级别，生成报告并可导出 Excel

## 常见问题

### 图表里中文显示成方块（□□）

程序默认使用 macOS 字体绘制图表。若在 Windows 上图表中文显示异常，需要把 `config.py` 中 `VIZ_DEFAULTS` 里的 `"font_family"` 改为 Windows 自带的字体，例如 `"Microsoft YaHei"`。

### 提示 `python` 不是内部或外部命令

说明安装 Python 时没勾选 "Add Python to PATH"。重新运行安装器，选择 "Modify"，勾选该选项即可；或卸载后重装。

### 安装库时报错

先确认 Python 版本是 3.11/3.12（在终端执行 `python --version` 查看）。若版本是 3.14 等过新版本，个别库可能无法安装，建议换装 3.11/3.12。
