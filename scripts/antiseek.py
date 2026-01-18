import base64
import io
import random
import os
from pathlib import Path
from modules import shared, script_callbacks, scripts as md_scripts, images
from modules.api import api
from modules.shared import opts
from scripts.core.core import process_image, get_random_seed, mix_seed, get_image_hash, generate_fake_image
from PIL import PngImagePlugin, _util, ImagePalette
from PIL import Image as PILImage
from io import BytesIO
from typing import Optional
from fastapi import FastAPI, Request, Response
from gradio import Blocks
import gradio as gr
import sys
from urllib.parse import unquote
import piexif
import piexif.helper

repo_dir = md_scripts.basedir()

if not hasattr(shared, 'antiseek_count'):
    shared.antiseek_count = 0

def on_ui_settings():
    section = ('antiseek', 'Anti-Seek (图像潜影)')

    shared.opts.add_option(
        "antiseek_salt",
        shared.OptionInfo(
            "", "Security Salt / 安全加盐",
            gr.Textbox,
            section=section
        ).info("Optional string to salt the random seed. / 可选字符串，用于混淆种子。")
    )

    shared.opts.add_option(
        "antiseek_keyname",
        shared.OptionInfo(
            "s_tag", "Metadata Key Name / 元数据键名",
            gr.Textbox,
            section=section
        ).info("The key name used to store the seed in metadata. Default: s_tag / 用于存储种子的元数据键名。默认：s_tag")
    )

def get_exif_bytes(pnginfo):
    exif_dict = {"0th": {}, "Exif": {}, "GPS": {}, "1st": {}, "thumbnail": None}
    
    geninfo = ""
    if pnginfo:
        for key in pnginfo.keys():
             if key == "parameters":
                 geninfo = pnginfo[key]
                 break
    
    if geninfo:
        user_comment = piexif.helper.UserComment.dump(geninfo, encoding="unicode")
        exif_dict["Exif"][piexif.ExifIFD.UserComment] = user_comment
        
    try:
        exif_bytes = piexif.dump(exif_dict)
    except:
        exif_bytes = b""
        
    return exif_bytes

def get_pil_format_from_ext(ext_str):
    if not ext_str.startswith('.'):
        ext_str = '.' + ext_str
    ext_str = ext_str.lower()
    try:
        if not PILImage.ID:
             PILImage.init()
        return PILImage.registered_extensions().get(ext_str, 'PNG')
    except:
        return 'PNG'

def hook_http_request(app: FastAPI):
    @app.middleware("http")
    async def image_decrypt_middleware(req: Request, call_next):
        endpoint: str = req.scope.get('path', 'err')
        endpoint = '/' + endpoint.strip('/')

        if endpoint.startswith('/infinite_image_browsing/image-thumbnail') or endpoint.startswith('/infinite_image_browsing/file'):
            query_string: str = req.scope.get('query_string', b'').decode('utf-8')
            query_string = unquote(query_string)
            if query_string and 'path=' in query_string:
                query = query_string.split('&')
                path = ''
                for sub in query:
                    if sub.startswith('path='):
                        path = sub[sub.index('=') + 1:]
                if path:
                    endpoint = '/file=' + path
        
        if endpoint.startswith('/sd_extra_networks/thumb'):
            query_string: str = req.scope.get('query_string', b'').decode('utf-8')
            query_string = unquote(query_string)
            if query_string and 'filename=' in query_string:
                query = query_string.split('&')
                path = ''
                for sub in query:
                    if sub.startswith('filename='):
                        path = sub[sub.index('=') + 1:]
                if path:
                    endpoint = '/file=' + path

        if endpoint.startswith('/file='):
            file_path = endpoint[6:] or ''
            if not file_path: return await call_next(req)
            if file_path.rfind('.') == -1: return await call_next(req)
            
            ext = file_path[file_path.rfind('.'):].lower()
            if ext in ['.png', '.jpg', '.jpeg', '.webp', '.bmp', '.avif']:
                try:
                    image = PILImage.open(file_path)
                    
                    if getattr(image, '_is_decrypted', False) or getattr(image, '_is_fake', False):
                        pnginfo_dict = image.info or {}
                        buffered = BytesIO()
                        
                        target_ext = pnginfo_dict.get('as_fmt', 'png')
                        pil_format = get_pil_format_from_ext(target_ext)
                        target_quality = int(pnginfo_dict.get('as_q', 90))
                        target_lossless = pnginfo_dict.get('as_l', 'False') == 'True'
                        
                        media_type = f"image/{target_ext if target_ext != 'jpg' else 'jpeg'}"
                        save_kwargs = {}

                        if pil_format == 'JPEG':
                            media_type = "image/jpeg"
                            save_kwargs['quality'] = target_quality
                            if image.mode in ('RGBA', 'LA'):
                                image = image.convert('RGB')
                            save_kwargs['exif'] = get_exif_bytes(pnginfo_dict)
                            
                        elif pil_format == 'WEBP':
                            media_type = "image/webp"
                            save_kwargs['quality'] = target_quality
                            if target_lossless:
                                save_kwargs['lossless'] = True
                            save_kwargs['exif'] = get_exif_bytes(pnginfo_dict)
                            
                        elif pil_format == 'AVIF':
                            media_type = "image/avif"
                            save_kwargs['quality'] = target_quality
                            save_kwargs['exif'] = get_exif_bytes(pnginfo_dict)
                            
                        elif pil_format == 'PNG':
                            media_type = "image/png"
                            info = PngImagePlugin.PngInfo()
                            for key in pnginfo_dict.keys():
                                if key not in [getattr(shared.opts, 'antiseek_keyname', 's_tag'), 'e_info', 'as_fmt', 'as_q', 'as_l'] and pnginfo_dict[key]:
                                    info.add_text(key, str(pnginfo_dict[key]))
                            save_kwargs['pnginfo'] = info
                        else:
                            pil_format = "PNG"
                            media_type = "image/png"

                        image.save(buffered, format=pil_format, **save_kwargs)
                        return Response(content=buffered.getvalue(), media_type=media_type)
                except:
                    pass
        
        return await call_next(req)

def app_started_callback(_: Blocks, app: FastAPI):
    app.middleware_stack = None
    hook_http_request(app)

    def get_encrypted_count():
        return {"count": getattr(shared, 'antiseek_count', 0)}

    app.add_api_route("/antiseek/count", get_encrypted_count, methods=["GET"])
    app.build_middleware_stack()

if getattr(PILImage.Image, '__name__', '') != 'AntiSeekImage':
    super_open = PILImage.open
    super_encode_pil_to_base64 = api.encode_pil_to_base64

    class AntiSeekImage(PILImage.Image):
        __name__ = "AntiSeekImage"
        
        @staticmethod
        def from_image(image: PILImage.Image):
            image = image.copy()
            img = AntiSeekImage()
            img.im = image.im
            img._mode = image.mode
            if image.im.mode:
                try:
                    img.mode = image.im.mode
                except: pass
            img._size = image.size
            img.format = image.format
            if image.mode in ("P", "PA"):
                if image.palette:
                    img.palette = image.palette.copy()
                else:
                    img.palette = ImagePalette.ImagePalette()
            img.info = image.info.copy()
            return img
            
        def save(self, fp, format=None, **params):
            filename = ""
            if isinstance(fp, Path):
                filename = str(fp)
            elif _util.is_path(fp):
                filename = fp
            elif fp == sys.stdout:
                try:
                    fp = sys.stdout.buffer
                except AttributeError:
                    pass
            if not filename and hasattr(fp, "name") and _util.is_path(fp.name):
                filename = fp.name
            
            if not filename:
                super().save(fp, format=format, **params)
                return

            if 'e_info' in self.info:
                super().save(fp, format=format, **params)
                return

            back_img = self.copy()
            
            orig_hash = get_image_hash(self)
            seed = get_random_seed()
            salt = getattr(shared.opts, 'antiseek_salt', '')
            key_name = getattr(shared.opts, 'antiseek_keyname', 's_tag') or 's_tag'
            
            eff_seed = mix_seed(seed, salt)
            encrypted = process_image(self, eff_seed)
            self.paste(encrypted)
            
            if hasattr(shared, 'antiseek_count'):
                shared.antiseek_count += 1
            else:
                shared.antiseek_count = 1
            
            self.format = PngImagePlugin.PngImageFile.format
            pnginfo = params.get('pnginfo', PngImagePlugin.PngInfo())
            if not pnginfo:
                pnginfo = PngImagePlugin.PngInfo()
                for key in (self.info or {}).keys():
                    if self.info[key]:
                        pnginfo.add_text(key, str(self.info[key]))
            
            fname_str = os.path.basename(filename)
            target_fmt = getattr(shared.opts, 'samples_format', 'png')
            
            if fname_str.startswith('grid-'):
                 target_fmt = getattr(shared.opts, 'grid_format', 'png')
            
            if not target_fmt: target_fmt = 'png'
            
            pnginfo.add_text('as_fmt', str(target_fmt))
            pnginfo.add_text('as_q', str(getattr(shared.opts, 'jpeg_quality', 80)))
            pnginfo.add_text('as_l', str(getattr(shared.opts, 'webp_lossless', False)))
            
            pnginfo.add_text(key_name, str(seed))
            pnginfo.add_text('e_info', orig_hash)
            params.update(pnginfo=pnginfo)
            
            super().save(fp, format=self.format, **params)
            
            self.paste(back_img)

    def open(fp, *args, **kwargs):
        image = super_open(fp, *args, **kwargs)
        pnginfo = image.info or {}
        
        if 'e_info' in pnginfo:
            try:
                key_name = getattr(shared.opts, 'antiseek_keyname', 's_tag') or 's_tag'
                salt = getattr(shared.opts, 'antiseek_salt', '')
                
                if key_name in pnginfo:
                    seed = int(pnginfo[key_name])
                    eff_seed = mix_seed(seed, salt)
                    decrypted = process_image(image, eff_seed)
                    
                    check_hash = get_image_hash(decrypted)
                    
                    if check_hash == pnginfo['e_info']:
                        pnginfo_clean = image.info.copy()
                        if key_name in pnginfo_clean: del pnginfo_clean[key_name]
                        if 'e_info' in pnginfo_clean: del pnginfo_clean['e_info']
                        
                        decrypted.info = pnginfo_clean
                        image = AntiSeekImage.from_image(image=decrypted)
                        image._is_decrypted = True
                        return image
                
                fake_img = generate_fake_image(image.width, image.height)
                fake_img.info = image.info
                image = AntiSeekImage.from_image(image=fake_img)
                image._is_fake = True
                return image
                
            except:
                fake_img = generate_fake_image(image.width, image.height)
                fake_img.info = image.info
                image = AntiSeekImage.from_image(image=fake_img)
                image._is_fake = True
                return image
                
        return AntiSeekImage.from_image(image=image)

    def encode_pil_to_base64(image: PILImage.Image):
        with io.BytesIO() as output_bytes:
            pnginfo = image.info or {}
            
            if 'e_info' in pnginfo:
                try:
                    key_name = getattr(shared.opts, 'antiseek_keyname', 's_tag') or 's_tag'
                    salt = getattr(shared.opts, 'antiseek_salt', '')
                    
                    if key_name in pnginfo:
                        seed = int(pnginfo[key_name])
                        eff_seed = mix_seed(seed, salt)
                        decrypted = process_image(image, eff_seed)
                        
                        if get_image_hash(decrypted) == pnginfo['e_info']:
                            image = decrypted
                        else:
                            image = generate_fake_image(image.width, image.height)
                    else:
                        image = generate_fake_image(image.width, image.height)
                except: 
                     image = generate_fake_image(image.width, image.height)
            
            target_ext = getattr(shared.opts, 'samples_format', 'png')
            if not target_ext: target_ext = 'png'
            
            pil_format = get_pil_format_from_ext(target_ext)
            target_quality = int(getattr(shared.opts, 'jpeg_quality', 80))
            target_lossless = getattr(shared.opts, 'webp_lossless', False)
            
            save_args = {}

            if pil_format == 'JPEG':
                if image.mode in ('RGBA', 'LA'):
                    image = image.convert('RGB')
                save_args['quality'] = target_quality
                save_args['exif'] = get_exif_bytes(image.info)
                
            elif pil_format == 'WEBP':
                save_args['quality'] = target_quality
                if target_lossless:
                    save_args['lossless'] = True
                save_args['exif'] = get_exif_bytes(image.info)
                
            elif pil_format == 'AVIF':
                save_args['quality'] = target_quality
                save_args['exif'] = get_exif_bytes(image.info)
            else:
                pil_format = 'PNG'

            image.save(output_bytes, format=pil_format, **save_args)
            bytes_data = output_bytes.getvalue()
            
        return base64.b64encode(bytes_data)

    _original_piexif_insert = piexif.insert
    
    def _antiseek_piexif_insert(exif, image, **kwargs):
        try:
            _original_piexif_insert(exif, image, **kwargs)
        except piexif.InvalidImageDataError:
            try:
                if isinstance(image, str) and os.path.isfile(image):
                    exif_dict = piexif.load(exif)
                    user_comment = exif_dict.get("Exif", {}).get(piexif.ExifIFD.UserComment)
                    
                    if user_comment:
                        parameters = piexif.helper.UserComment.load(user_comment)
                        if parameters:
                            with PILImage.open(image) as img_obj:
                                info = PngImagePlugin.PngInfo()
                                for k, v in (img_obj.info or {}).items():
                                    info.add_text(k, str(v))
                                info.add_text("parameters", parameters)
                                
                                img_obj.save(image, format="PNG", pnginfo=info)
            except:
                pass
        except Exception:
            raise

    piexif.insert = _antiseek_piexif_insert

    PILImage.Image = AntiSeekImage
    PILImage.open = open
    api.encode_pil_to_base64 = encode_pil_to_base64

script_callbacks.on_ui_settings(on_ui_settings)
script_callbacks.on_app_started(app_started_callback)

def print_obfuscated(msg):
    charmap = {
    'A': ['Α', 'А', 'Ａ'],
    'n': ['ｎ', 'η', 'ո', 'и'],
    't': ['ｔ', 'τ', '†', 'т'],
    'i': ['ｉ', '¡', 'í'],
    'S': ['Ｓ', 'Ѕ', '§'],
    'e': ['ｅ', 'е', 'є', 'é'],
    'k': ['ｋ', 'κ', 'к'],
    'P': ['Ｐ', 'Ρ', 'Р', 'Þ'],
    'l': ['ｌ', 'ǀ', '1', 'I'],
    'u': ['ｕ', 'υ', 'μ'],
    'g': ['ｇ', 'ɡ'],
    'c': ['ｃ', 'с', 'ς'],
    'v': ['ｖ', 'ν'],
    'T': ['Ｔ', 'Τ', 'Т'],
    'X': ['Ｘ', 'Χ', 'Х'],
    'Y': ['Ｙ', 'Υ'],
    '-': ['－', '—', 'ㄧ', '–'],
    '!': ['！', 'ǃ', '‼'],
    ' ': ['\u2000', '\u2002', '\u3000', '\u2009']
    }
    invisible = ['\u200b', '\u200c', '\u200d', '\u2060', '\uFEFF']
    out = []
    for char in msg:
        if char in charmap and random.random() > 0.15:
            c = random.choice(charmap[char])
        elif '!' <= char <= '~' and random.random() > 0.4:
            c = chr(ord(char) + 0xFEE0)
        else:
            c = char
        out.append(c)
        for _ in range(random.randint(0, 5)):
            out.append(random.choice(invisible))
    print("".join(out))

print_obfuscated('Anti-Seek Plugin Active!')