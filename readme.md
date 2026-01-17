# 图像潜影 (Anti-Seek)

这是一个为 Stable Diffusion WebUI 开发的**防检测**与**隐私保护**插件。

### 核心理念

本插件的核心目的是为了防止图像被机器扫描或未授权查看。它引入了**混淆**机制：当解密失败或被探测时，它会伪造出一张随机的几何图形图片，以此迷惑监测系统。

### 灵感来源

这个项目的灵感和基础逻辑主要来自大佬的 [viyiviyi/sd-encrypt-image](https://github.com/viyiviyi/sd-encrypt-image) 项目。

### 核心原理

1.  **噪声加密**：利用 NumPy 生成一层基于特定种子的“数字噪声”，通过异或（XOR）运算将噪声“盖”在原图上。
2.  **哈希校验**：加密时会计算原图的哈希值并存储（`e_info`），解密时用于验证数据完整性。
3.  **安全加盐**：支持用户自定义“盐（Salt）”值，用于混淆随机种子。即使算法公开，不知道盐值也无法还原图片。
4.  **伪造机制**：如果解密时发现哈希不匹配、盐值错误或键名错误，插件将自动生成一张包含随机颜色和几何图形的**伪造图片**，达到混淆视听的效果。

### WebUI 功能设置

在 WebUI 的设置页面中，你可以配置以下选项：

*   **传输预览格式**：支持 PNG/JPEG/WEBP/AVIF。
    *   *注意：非 PNG 格式传输会导致元数据（GenInfo）在预览或 API 响应中丢失。*
*   **安全加盐 (Security Salt)**：设置一个自定义字符串。只有拥有相同盐值的客户端/CLI 才能还原图片。
*   **元数据键名 (Metadata Key Name)**：自定义存储种子的键名（默认为 `s_tag`），防止被轻易扫描定位。

### 命令行工具 (tools/cli.py)

该命令行工具可以将加密的图片还原为原图，也可以对普通图片进行加密。它完全支持 WebUI 中设置的加盐和键名参数。

#### 环境要求

请确保已安装 **NumPy** 与 **Pillow** 模块。

```bash
pip install numpy Pillow
```

#### 参数说明

| 参数 | 简写 | 说明 | 默认值 |
| :--- | :--- | :--- | :--- |
| `--input` | `-i` | 输入目录路径 (必选) | 无 |
| `--output` | `-o` | 输出目录路径 | 输入目录下的 `processed` 文件夹 |
| `--threads` | `-t` | 并发处理线程数 | 自动分配 |
| `--salt` | `-s` | **安全加盐字符串** (需与加密时一致) | 空字符串 |
| `--keyname` | `-k` | **元数据键名** (需与加密时一致) | `s_tag` |

#### 使用示例

1.  **基础用法**（无盐，默认键名）：
    ```bash
    python tools/cli.py -i F:/sources
    ```

2.  **解密带“盐”的图片**（假设你在 WebUI 设置了盐值为 `my_secret`）：
    ```bash
    python tools/cli.py -i ./encrypted_imgs --salt "my_secret"
    ```

3.  **完全自定义解密**（指定输出目录、自定义键名 `hidden_seed` 和盐）：
    ```bash
    python tools/cli.py -i ./input -o ./output --keyname "hidden_seed" --salt "complex_password_123"
    ```

4.  **多线程加速**：
    ```bash
    python tools/cli.py -i ./photos -t 16
    ```