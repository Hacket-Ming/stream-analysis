# macOS 环境配置实录（Homebrew 路径）

记录在 macOS (Apple Silicon, Darwin 25.4) 上把 `stream-analysis` 跑起来的实际步骤，**含踩到的坑**。

适用条件：只做 H.264/H.265/H.266 码流**分析**（用现成 `.mp4` / `.265` / `.266` 文件）。
**不适用**：需要自己用 `libvvenc` 编 `.266` 测试码流 —— 那条走 [FFmpeg-Build-Guide.md](FFmpeg-Build-Guide.md) 源码路径。

完成日期：2026-05-16

---

## 1. 初始系统状态

```
Homebrew 5.1.9 (Apple Silicon, /opt/homebrew)
ffmpeg / ffprobe : 未安装
python3          : 3.9.5  @ /usr/local/bin/python3   ← Intel-time 残留安装
pip3             : 21.1.1
/opt/homebrew/   : 仅有 openssl@3，没有任何 Python
```

需要满足的依赖（来自 `README.md` + `pyproject.toml`）：
- FFmpeg（解封装 + ffprobe 帧信息；H.266 还需要 ≥ n7.0 的原生 VVC 解码）
- Python ≥ 3.10

---

## 2. 实际安装步骤

### 2.1 装 FFmpeg

```bash
brew install ffmpeg
```

拉了 10 个依赖（dav1d, lame, libvmaf, libvpx, openssl@3, opus, sdl2, svt-av1, x264, x265）+ ffmpeg 本体。Apple Silicon bottle，无需编译，从 USTC 镜像下载。耗时几分钟。

**得到**：`ffmpeg 8.1.1` / `ffprobe 8.1.1` @ `/opt/homebrew/bin/`。

验证：

```bash
ffmpeg -decoders 2>/dev/null | grep -E " (h264|hevc|vvc) "
# VFS..D h264   H.264 / AVC / MPEG-4 AVC / MPEG-4 part 10
# VFS..D hevc   HEVC (High Efficiency Video Coding)
# V....D vvc    VVC (Versatile Video Coding)             ← 原生 VVC 解码就位
```

### 2.2 装 Python 3.13

```bash
brew install python@3.13
```

**得到**：`/opt/homebrew/bin/python3.13` (3.13.13) + `pip 26.1`。Homebrew 不会把 `python3` 软链覆盖到 3.13，需要显式叫 `python3.13` / `pip3.13`。

### 2.3 装 `stream-analysis`（editable）

```bash
cd ~/Codes/projects/stream-analysis
/opt/homebrew/bin/pip3.13 install --break-system-packages -e .
```

**得到**：`stream-analysis` CLI @ `/opt/homebrew/bin/stream-analysis`，指向 Python 3.13。

### 2.4 装 pytest（运行测试用）

```bash
/opt/homebrew/bin/pip3.13 install --break-system-packages pytest
```

---

## 3. 验证

```bash
# CLI
stream-analysis --help

# 单元测试
/opt/homebrew/bin/python3.13 -m pytest tests/ -q
# 39 passed in 0.02s

# 端到端：用 ffmpeg 生成最小 H.264 → 解析
ffmpeg -f lavfi -i testsrc=duration=1:size=160x90:rate=10 \
  -c:v libx264 -preset ultrafast -frames:v 5 -y /tmp/test.h264
stream-analysis /tmp/test.h264 --format csv
# 解析出 SPS / PPS / SEI / IDR + 4×P slice，5 帧 ffprobe 信息齐
```

---

## 4. 踩到的坑

### 4.1 README 说的 `pip3 install --break-system-packages -e .` 直接跑会失败

```
no such option: --break-system-packages
```

**原因**：当前 PATH 上的 `pip3` 是 21.1.1（来自 `/usr/local/bin/python3` 那套老 Intel Homebrew 安装），早于 PEP 668。`--break-system-packages` 是 pip 23.0+ 才有的开关。

**解法**：等装完 Python 3.13 之后，**显式用 `pip3.13`**：
```bash
/opt/homebrew/bin/pip3.13 install --break-system-packages -e .
```

README 那条命令的隐含前提是"你用的是 Homebrew 的现役 Python"，老 Python 3.9 不满足这条。

### 4.2 项目要求 Python ≥ 3.10，系统 Python 是 3.9.5

`pyproject.toml` 写了 `requires-python = ">=3.10"`。3.9 上 `pip install -e .` 会被拒。

**解法**：`brew install python@3.13`。装新的，不替换老的（`/usr/local/bin/python3` 保持 3.9）。

### 4.3 `brew install ffmpeg` 不会顺带装 Python

我一开始下意识以为 ffmpeg 会带 Python（错觉）。实际 Homebrew 的 ffmpeg formula 依赖里**没有** Python。Python 这一步要单独装。

### 4.4 `pip3.13` 不在默认 PATH

`brew install python@3.13` 完成后给出提示：
> `python3.13`, `python3.13-config`, `pip3.13` etc. are installed into
> `/opt/homebrew/opt/python@3.13/libexec/bin`

但实际 `/opt/homebrew/bin/python3.13` 和 `/opt/homebrew/bin/pip3.13` 是有的（Homebrew 自动 linked 了带版本号的入口）。不带版本号的 `python3` / `pip3` 仍然指向老的 3.9 —— 这是设计如此（避免覆盖）。

**结论**：跟这台机器协作时，所有 stream-analysis 相关的 Python 调用都要走带版本号的 `python3.13` / `pip3.13`，或者直接走 `/opt/homebrew/bin/stream-analysis`。

### 4.5 USTC 镜像（环境特性，不是问题）

Homebrew 已经配置走 `mirrors.ustc.edu.cn`。bottle 下载速度正常。

---

## 5. 系统现状（安装后）

| 软件 | 路径 | 版本 |
|---|---|---|
| ffmpeg / ffprobe | `/opt/homebrew/bin/` | 8.1.1 |
| python3 | `/usr/local/bin/python3` | 3.9.5（**未动**） |
| python3.13 | `/opt/homebrew/bin/python3.13` | 3.13.13（**新增**） |
| pip3 | `/usr/local/bin/pip3` | 21.1.1（**未动**） |
| pip3.13 | `/opt/homebrew/bin/pip3.13` | 26.1（**新增**） |
| stream-analysis | `/opt/homebrew/bin/stream-analysis` | 0.1.0 (editable) → Python 3.13 |
| pytest | site-packages of Python 3.13 | 9.0.3 |

---

## 6. 没做的事

- **`libvvenc` / VVC 编码**：Homebrew ffmpeg 8.1.1 不含 vvenc。要自己 `ffmpeg -c:v libvvenc ... output.266` 才需要走源码编译。**只读 / 分析 `.266` 文件不需要这个**（原生 VVC 解码已就位）。
- **替换系统 Python 3.9.5**：不需要，留着无妨；新 Python 走带版本号入口。
- **加 PATH alias**：没改 shell 配置；要更顺手可以 `alias python3=/opt/homebrew/bin/python3.13`，但全局这么做会影响其他用 3.9 的项目。
