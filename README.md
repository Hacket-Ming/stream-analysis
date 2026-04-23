# Stream Analysis

H.264/H.265 码流语法字段分析工具。解析视频码流中的所有 NAL Unit 语法元素（不含 slice data），输出为 JSON/CSV 表格，并提供帧级解码序与显示序信息。

## 功能

- **H.264 解析**：SPS、PPS、SEI、Slice Header、AUD、Filler、EOS 等全部 NAL 类型
- **H.265 解析**：VPS、SPS、PPS、SEI、Slice Header、AUD、EOS、EOB 等全部 NAL 类型
- **封装格式支持**：所有 ffmpeg 支持的封装格式（MP4、FLV、MKV、TS 等），自动解封装为裸流
- **裸流支持**：直接解析 `.264`/`.h264`/`.265`/`.h265` 裸流文件
- **帧序信息**：通过 ffprobe 获取每帧的解码序（decoding order）、显示序（display order）、PTS/DTS、帧类型
- **多种输出格式**：JSON（完整结构化）、CSV 摘要、CSV 完整字段、CSV 帧序表

## 依赖

- Python >= 3.10
- FFmpeg（系统安装，用于封装格式解封装和帧信息提取）
- 零 Python 外部依赖，仅使用标准库

## 安装

```bash
pip install -e .
```

或直接以模块方式运行，无需安装：

```bash
python3 -m stream_analysis <input_file> [options]
```

## 使用

```bash
# JSON 输出（包含 NAL 解析 + 帧序信息）
stream-analysis input.mp4 -o output.json

# CSV NAL 摘要
stream-analysis input.264 -o summary.csv

# CSV 所有语法字段展开
stream-analysis input.265 --format csv-full -o full.csv

# CSV 帧序表（decode/display order）
stream-analysis input.mp4 --format csv-frames -o frames.csv

# 输出到终端
stream-analysis input.mp4 --format csv

# 指定视频流索引（多流容器）
stream-analysis input.mkv -o output.json --stream 1

# 强制指定编码类型
stream-analysis input.bin -o output.json --codec h265
```

## 输出示例

### CSV 摘要

```
index,offset,size,nal_unit_type,nal_unit_type_name,key_info
0,0,24,32,VPS,profile=1(Main) level=2.0
1,28,42,33,SPS,640x480 chroma=4:2:0
2,74,7,34,PPS,pps_id=0
3,85,2306,39,SEI (prefix),user_data_unregistered
4,2395,3593,20,IDR_N_LP,type=I QP=33
5,5992,162,1,TRAIL_R,type=P QP=33
6,6158,206,1,TRAIL_R,type=P QP=33
7,6368,87,1,TRAIL_R,type=B QP=35
```

### CSV 帧序表

```
decode_order,display_order,pict_type,key_frame,pts,pts_time,dts,dts_time
0,0,I,True,0,0.000000,0,0.000000
1,3,P,False,3072,0.120000,512,0.040000
2,1,B,False,1024,0.080000,1024,0.080000
3,2,B,False,1536,0.060000,1536,0.060000
```

### JSON（部分）

```json
{
  "stream_info": {
    "file": "input.mp4",
    "codec": "H264",
    "width": 1920,
    "height": 1080,
    "total_nal_units": 150
  },
  "nal_units": [
    {
      "index": 0,
      "nal_unit_type": 7,
      "nal_unit_type_name": "SPS",
      "syntax_elements": {
        "profile_idc": 100,
        "profile_name": "High",
        "level": "4.0",
        "derived_width": 1920,
        "derived_height": 1080,
        "chroma_format_idc": 1
      }
    }
  ],
  "frames": [
    {
      "decode_order": 0,
      "display_order": 0,
      "pict_type": "I",
      "key_frame": true,
      "pts_time": "0.000000"
    }
  ]
}
```

## 解析范围

### H.264

| NAL Type | 名称 | 解析内容 |
|----------|------|----------|
| 7 | SPS | profile/level、分辨率、chroma、bit depth、POC 类型、VUI（含 HRD、timing）、scaling list |
| 8 | PPS | entropy mode、ref idx、weighted pred、deblocking、transform_8x8 |
| 1-5 | Slice Header | slice type、frame_num、POC、ref pic list、weight table、QP、deblocking 参数 |
| 6 | SEI | user_data_unregistered、recovery_point、mastering display、content light level 等 |
| 9 | AUD | primary_pic_type |
| 10-12 | 其他 | End of Sequence、End of Stream、Filler Data |

### H.265

| NAL Type | 名称 | 解析内容 |
|----------|------|----------|
| 32 | VPS | profile_tier_level、timing info、sub-layer ordering |
| 33 | SPS | 分辨率、chroma、bit depth、short_term_ref_pic_set、long-term ref、VUI、scaling list |
| 34 | PPS | tiles 配置、entropy sync、QP offset、deblocking |
| 0-21 | Slice Header | slice type、POC、st_rps 选择、temporal MVP、SAO、QP、deblocking |
| 39/40 | SEI | 同 H.264 SEI payload 类型 |
| 35-38 | 其他 | AUD、EOS、EOB、Filler Data |

## 项目结构

```
stream_analysis/
├── stream_analysis/
│   ├── __main__.py          # python -m 入口
│   ├── cli.py               # CLI 接口
│   ├── bitreader.py         # 位级读取 + Exp-Golomb 解码
│   ├── nal.py               # NAL unit 提取、起始码检测、EPB 移除
│   ├── detect.py            # 编码/文件类型自动检测
│   ├── demux.py             # ffmpeg 解封装
│   ├── frame_info.py        # 帧级 decode/display order
│   ├── h264/                # H.264 子解析器
│   ├── h265/                # H.265 子解析器
│   └── output/              # JSON/CSV 输出格式化
├── tests/                   # 单元测试
└── pyproject.toml
```

## License

MIT
