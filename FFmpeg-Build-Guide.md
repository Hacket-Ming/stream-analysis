
# FFmpeg 源码编译安装（macOS）

支持 H.264 (libx264) + H.265 (libx265) + H.266/VVC (libvvenc) 编码，VVC 原生解码。

最后更新：2026-04-25

---

## 环境概览

| 组件 | 版本 | 源码路径 | 安装路径 |
|------|------|----------|----------|
| FFmpeg | master (N-124094-g45fe315cf0) | `~/git/FFmpeg` | `~/git/FFmpeg/build` |
| x264 | latest | `~/git/x264` | `~/git/x264/build` |
| x265 | latest | `~/git/x265_git` | `~/git/x265_git/build/xcode/build` (macOS) |
| vvenc | 1.15.0-dev | `~/git/vvenc` | `~/git/vvenc/build/install` |

系统 PATH 通过符号链接指向 FFmpeg 源码目录下的可执行文件：
```
/usr/local/bin/ffmpeg  -> ~/git/FFmpeg/ffmpeg
/usr/local/bin/ffplay  -> ~/git/FFmpeg/ffplay
/usr/local/bin/ffprobe -> ~/git/FFmpeg/ffprobe
```

---

## 1. 编译 x264（静态库）

```bash
cd ~/git
git clone https://code.videolan.org/videolan/x264.git
cd ~/git/x264
./configure --prefix=$(pwd)/build \
  --disable-asm --disable-cli --disable-shared --enable-static
make -j10 && make install
```

pkgconfig: `~/git/x264/build/lib/pkgconfig/x264.pc`

## 2. 编译 x265（静态库）

```bash
cd ~/git
git clone https://bitbucket.org/multicoreware/x265_git.git
cd ~/git/x265_git/build/xcode    # macOS 用 xcode 目录，Linux 用 linux 目录
cmake -DCMAKE_INSTALL_PREFIX=$(pwd)/build -DENABLE_SHARED=OFF ../../source
make -j10 && make install
```

pkgconfig: `~/git/x265_git/build/xcode/build/lib/pkgconfig/x265.pc`

## 3. 编译 vvenc（静态库，H.266/VVC 编码器）

```bash
cd ~/git
git clone https://github.com/fraunhoferhhi/vvenc.git
cd ~/git/vvenc
mkdir -p build && cd build
cmake .. -DCMAKE_INSTALL_PREFIX=$(pwd)/install \
         -DCMAKE_BUILD_TYPE=Release \
         -DBUILD_SHARED_LIBS=OFF
make -j10 && make install
```

pkgconfig: `~/git/vvenc/build/install/lib/pkgconfig/libvvenc.pc`

## 4. 编译 FFmpeg

```bash
cd ~/git/FFmpeg
git fetch origin
git checkout master    # libvvenc 支持仅在 master 分支（n7.0 tag 中没有）

make clean

env PKG_CONFIG_PATH=\
~/git/x264/build/lib/pkgconfig:\
~/git/x265_git/build/xcode/build/lib/pkgconfig:\
~/git/vvenc/build/install/lib/pkgconfig \
./configure \
  --prefix=$(pwd)/build \
  --enable-gpl --enable-nonfree --enable-pthreads --extra-libs=-lpthread \
  --disable-asm --disable-x86asm --disable-inline-asm \
  --enable-decoder=aac --enable-decoder=aac_fixed --enable-decoder=aac_latm --enable-encoder=aac \
  --enable-libx264 --enable-libx265 \
  --enable-libvvenc \
  --pkg-config-flags='--static' \
  --enable-sdl --enable-ffplay

make -j10
make install   # 可选，安装到 ~/git/FFmpeg/build/bin/
```

### configure 参数说明

| 参数 | 说明 |
|------|------|
| `--enable-libx264` | H.264 编码 |
| `--enable-libx265` | H.265/HEVC 编码 |
| `--enable-libvvenc` | H.266/VVC 编码（需 libvvenc >= 1.6.1） |
| `--disable-asm` | 禁用汇编优化（跨平台兼容） |
| `--enable-sdl --enable-ffplay` | 启用 ffplay 播放器（需系统安装 SDL2） |
| `--pkg-config-flags='--static'` | 静态链接外部库 |

---

## 5. 验证

```bash
# 版本信息
ffmpeg -version

# 编码器列表
ffmpeg -encoders 2>/dev/null | grep -E "libx264|libx265|libvvenc"
# V....D libx264     libx264 H.264 / AVC
# V....D libx265     libx265 H.265 / HEVC
# V....D libvvenc    libvvenc H.266 / VVC

# VVC 原生解码器（内置，无需外部库）
ffmpeg -decoders 2>/dev/null | grep vvc
# V....D vvc         VVC (Versatile Video Coding)

# VVC 编码测试
ffmpeg -f lavfi -i testsrc=duration=1:size=64x64:rate=10 \
  -c:v libvvenc -frames:v 3 /tmp/test.266

# VVC 解码测试
ffmpeg -i /tmp/test.266 -f null -

# VVC 播放测试
ffplay /tmp/test.266
```

---

## 备注

- **RTMP H.265**：FFmpeg n7.0+ 已原生支持 enhanced FLV/HEVC，不再需要 runner365 补丁（之前 n5.1.2 需要手动打补丁）
- **VVC 解码**：FFmpeg n7.0 起内置原生 VVC 解码器，不需要外部 libvvdec
- **VVC 编码**：`--enable-libvvenc` 截至 2026-04 仍仅在 master 分支，尚未进入 release tag
- **编码速度**：VVC 编码比 H.265 慢很多，测试时建议用小分辨率和少量帧
- **历史版本**：之前使用 n5.1.2 + runner365 RTMP H.265 补丁，已升级废弃
