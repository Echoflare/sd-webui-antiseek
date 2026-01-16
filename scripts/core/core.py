import numpy as np
from PIL import Image

def get_random_seed():
    return int(np.random.randint(0, 4294967295, dtype=np.uint32))

def process_image(image, seed):
    img_array = np.array(image)
    rng = np.random.default_rng(seed)
    noise = rng.integers(0, 256, img_array.shape, dtype=np.uint8)
    processed_array = np.bitwise_xor(img_array, noise)
    return Image.fromarray(processed_array)