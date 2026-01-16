import os
import sys
import argparse
import numpy as np
from concurrent.futures import ThreadPoolExecutor
from PIL import Image, PngImagePlugin

def get_random_seed():
    return int(np.random.randint(0, 4294967295, dtype=np.uint32))

def process_image(image, seed):
    img_array = np.array(image)
    rng = np.random.default_rng(seed)
    noise = rng.integers(0, 256, img_array.shape, dtype=np.uint8)
    processed_array = np.bitwise_xor(img_array, noise)
    return Image.fromarray(processed_array)

def process_worker(file_path, output_dir):
    try:
        image = Image.open(file_path)
        pnginfo = image.info or {}
        
        filename = os.path.basename(file_path)
        name_root, _ = os.path.splitext(filename)
        save_path = os.path.join(output_dir, name_root + '.png')

        info = PngImagePlugin.PngInfo()
        
        if 's_tag' in pnginfo:
            seed = int(pnginfo['s_tag'])
            result_img = process_image(image, seed)
            
            for key, value in pnginfo.items():
                if key != 's_tag':
                    info.add_text(key, str(value))
            
            mode = "Decrypted"
        else:
            seed = get_random_seed()
            result_img = process_image(image, seed)
            
            for key, value in pnginfo.items():
                info.add_text(key, str(value))
            info.add_text('s_tag', str(seed))
            
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
    parser.add_argument('-t', '--threads', type=int, default=8, help="工作线程数")
    
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
                    tasks.append(executor.submit(process_worker, file_path, output_dir))
    
    for task in tasks:
        task.result()

if __name__ == "__main__":
    main()