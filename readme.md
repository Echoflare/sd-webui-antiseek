# 图像潜影 (Anti-Seek)

这是一个为 Stable Diffusion WebUI 开发的**防检测**插件。

### 核心理念

本插件的作用是为了防检测而加密，而非为了加密而加密，所以它不需要手动设置密码。

### 灵感来源

这个项目的灵感和基础逻辑主要来自大佬的 [viyiviyi/sd-encrypt-image](https://github.com/viyiviyi/sd-encrypt-image) 项目。

### 核心原理

利用 NumPy 直接生成一层“数字噪声”。通过异或（XOR）运算，把这层噪声“盖”在原图上。

生成噪声用的随机“种子”会被自动写入图片的元数据里，插件根据元数据判断图片是否已被加密。

### 命令行工具 (tools/cli.py)

该命令行工具可以将加密的图片还原为原图，同时也可以对元数据中没有加密信息的图片进行加密。

#### 环境要求

请确保已安装 **NumPy** 与 **Pillow** 模块。

```
pip install numpy Pillow
```

#### 使用方法

打开终端，运行：

```bash
# 1. 基础用法：指定输入目录（默认输出到 input_dir/processed）
python tools/cli.py -i F:/sources

# 2. 指定输出目录
python tools/cli.py -i ./input -o ./output

# 3. 多线程加速（默认 8 线程）
python tools/cli.py -i ./photos -t 16
```