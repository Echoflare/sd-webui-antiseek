import os
import sys
import argparse
import numpy as np
import hashlib
import random
from concurrent.futures import ThreadPoolExecutor
from PIL import Image, PngImagePlugin, ImageDraw

def get_random_seed():
    return int(np.random.randint(0, 4294967295, dtype=np.uint32))

def mix_seed(seed, salt):
    if not salt:
        return seed
    payload = f"{seed}{salt}"
    h = hashlib.sha256(payload.encode('utf-8')).hexdigest()
    return int(h[:8], 16)

def get_image_hash(image):
    return hashlib.md5(image.tobytes()).hexdigest()

def process_image(image, seed):
    img_array = np.array(image)
    rng = np.random.default_rng(seed)
    noise = rng.integers(0, 256, img_array.shape, dtype=np.uint8)
    processed_array = np.bitwise_xor(img_array, noise)
    return Image.fromarray(processed_array)

def generate_fake_image(width, height):
    bg_color = (random.randint(0, 255), random.randint(0, 255), random.randint(0, 255))
    img = Image.new('RGB', (width, height), bg_color)
    draw = ImageDraw.Draw(img, 'RGBA')
    
    for _ in range(random.randint(20, 50)):
        shape_type = random.choice(['rect', 'ellipse', 'polygon'])
        color = (random.randint(0, 255), random.randint(0, 255), random.randint(0, 255), random.randint(100, 255))
        
        if shape_type == 'rect':
            x1 = random.randint(0, width)
            y1 = random.randint(0, height)
            x2 = random.randint(0, width)
            y2 = random.randint(0, height)
            draw.rectangle([min(x1,x2), min(y1,y2), max(x1,x2), max(y1,y2)], fill=color)
        elif shape_type == 'ellipse':
            x1 = random.randint(0, width)
            y1 = random.randint(0, height)
            x2 = random.randint(0, width)
            y2 = random.randint(0, height)
            draw.ellipse([min(x1,x2), min(y1,y2), max(x1,x2), max(y1,y2)], fill=color)
        elif shape_type == 'polygon':
            points = []
            for _ in range(random.randint(3, 6)):
                points.append((random.randint(0, width), random.randint(0, height)))
            draw.polygon(points, fill=color)
            
    return img

def process_worker(file_path, output_dir, salt, key_name):
    try:
        image = Image.open(file_path)
        pnginfo = image.info or {}
        
        filename = os.path.basename(file_path)
        name_root, _ = os.path.splitext(filename)
        save_path = os.path.join(output_dir, name_root + '.png')

        info = PngImagePlugin.PngInfo()
        
        if 'e_info' in pnginfo:
            if key_name in pnginfo:
                try:
                    seed = int(pnginfo[key_name])
                    eff_seed = mix_seed(seed, salt)
                    result_img = process_image(image, eff_seed)
                    
                    if get_image_hash(result_img) == pnginfo['e_info']:
                        for key, value in pnginfo.items():
                            if key != key_name and key != 'e_info':
                                info.add_text(key, str(value))
                        mode = "Decrypted"
                    else:
                        result_img = generate_fake_image(image.width, image.height)
                        mode = "Fake(HashMismatch)"
                except:
                    result_img = generate_fake_image(image.width, image.height)
                    mode = "Fake(Error)"
            else:
                result_img = generate_fake_image(image.width, image.height)
                mode = "Fake(KeyMissing)"
                
        else:
            orig_hash = get_image_hash(image)
            seed = get_random_seed()
            eff_seed = mix_seed(seed, salt)
            result_img = process_image(image, eff_seed)
            
            for key, value in pnginfo.items():
                info.add_text(key, str(value))
            
            info.add_text(key_name, str(seed))
            info.add_text('e_info', orig_hash)
            
            mode = "Encrypted"

        result_img.save(save_path, format="PNG", pnginfo=info)
        print(f"[{mode}] {filename}")
        return True

    except Exception as e:
        print(f"[Error] {file_path}: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description="Anti-Seek 图像潜影批处理工具")
    parser.add_argument('-i', '--input', required=True, help="输入目录")
    parser.add_argument('-o', '--output', default=None, help="输出目录")
    parser.add_argument('-t', '--threads', type=int, default=None, help="工作线程数")
    parser.add_argument('-s', '--salt', default="", help="安全加盐字符串")
    parser.add_argument('-k', '--keyname', default="s_tag", help="元数据键名 (默认: s_tag)")
    
    args = parser.parse_args()
    
    input_dir = args.input
    output_dir = args.output if args.output else os.path.join(input_dir, 'processed')
    
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        
    tasks = []
    valid_exts = ('.png', '.jpg', '.jpeg', '.webp', '.bmp')
    
    with ThreadPoolExecutor(max_workers=args.threads) as executor:
        for root, _, files in os.walk(input_dir):
            if os.path.abspath(root) == os.path.abspath(output_dir):
                continue
                
            for file in files:
                if file.lower().endswith(valid_exts):
                    file_path = os.path.join(root, file)
                    tasks.append(executor.submit(process_worker, file_path, output_dir, args.salt, args.keyname))
    
    for task in tasks:
        task.result()

if __name__ == "__main__":
    main()