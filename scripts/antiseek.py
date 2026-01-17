import base64
import io
from pathlib import Path
from modules import shared, script_callbacks, scripts as md_scripts, images
from modules.api import api
from modules.shared import opts
from scripts.core.core import process_image, get_random_seed
from PIL import PngImagePlugin, _util, ImagePalette
from PIL import Image as PILImage
from io import BytesIO
from typing import Optional
from fastapi import FastAPI, Request, Response
from gradio import Blocks
import gradio as gr
import sys
from urllib.parse import unquote

try:
    import piexif
    import piexif._exceptions
except ImportError:
    piexif = None

repo_dir = md_scripts.basedir()
total_encrypted_count = 0

def on_ui_settings():
    section = ('antiseek', 'Anti-Seek (图像潜影)')
    
    shared.opts.add_option(
        "antiseek_preview_format",
        shared.OptionInfo(
            "png", "Frontend Preview/API Format / 前端预览及API格式",
            gr.Dropdown, lambda: {"choices": ["png", "jpeg", "webp", "avif"]},
            section=section
        ).info("Warning: Non-PNG formats will cause metadata (GenInfo) loss in preview/API. / 警告：非 PNG 格式会导致预览或 API 返回的图片丢失元数据。")
    )
    
    shared.opts.add_option(
        "antiseek_preview_quality",
        shared.OptionInfo(
            90, "Preview Compression Quality / 预览压缩质量",
            gr.Slider, {"minimum": 10, "maximum": 100, "step": 1},
            section=section
        ).info("Valid for JPEG/WEBP/AVIF. 100 triggers lossless for WEBP. / 适用于 JPEG/WEBP/AVIF。WEBP 设置为 100 时启用无损压缩。")
    )

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
                    
                    if getattr(image, '_is_decrypted', False):
                        pnginfo = image.info or {}
                        buffered = BytesIO()
                        
                        target_format = getattr(shared.opts, 'antiseek_preview_format', 'png').lower()
                        target_quality = int(getattr(shared.opts, 'antiseek_preview_quality', 90))
                        
                        save_kwargs = {}
                        media_type = "image/png"
                        pil_format = "PNG"

                        if target_format == 'jpeg':
                            media_type = "image/jpeg"
                            pil_format = "JPEG"
                            save_kwargs['quality'] = target_quality
                            if image.mode in ('RGBA', 'LA'):
                                image = image.convert('RGB')
                        elif target_format == 'webp':
                            media_type = "image/webp"
                            pil_format = "WEBP"
                            save_kwargs['quality'] = target_quality
                            if target_quality >= 100:
                                save_kwargs['lossless'] = True
                        elif target_format == 'avif':
                            media_type = "image/avif"
                            pil_format = "AVIF"
                            save_kwargs['quality'] = target_quality
                        else:
                            info = PngImagePlugin.PngInfo()
                            for key in pnginfo.keys():
                                if key != 's_tag' and pnginfo[key]:
                                    info.add_text(key, str(pnginfo[key]))
                            save_kwargs['pnginfo'] = info

                        image.save(buffered, format=pil_format, **save_kwargs)
                        return Response(content=buffered.getvalue(), media_type=media_type)
                except:
                    pass
        
        return await call_next(req)

def app_started_callback(_: Blocks, app: FastAPI):
    app.middleware_stack = None
    hook_http_request(app)
    
    def get_encrypted_count():
        return {"count": total_encrypted_count}
    
    app.add_api_route("/antiseek/count", get_encrypted_count, methods=["GET"])
    app.build_middleware_stack()

if PILImage.Image.__name__ != 'AntiSeekImage':
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

            if 's_tag' in self.info:
                super().save(fp, format=format, **params)
                return

            back_img = self.copy()
            
            seed = get_random_seed()
            encrypted = process_image(self, seed)
            self.paste(encrypted)
            
            global total_encrypted_count
            total_encrypted_count += 1
            
            self.format = PngImagePlugin.PngImageFile.format
            pnginfo = params.get('pnginfo', PngImagePlugin.PngInfo())
            if not pnginfo:
                pnginfo = PngImagePlugin.PngInfo()
                for key in (self.info or {}).keys():
                    if self.info[key]:
                        pnginfo.add_text(key, str(self.info[key]))
            
            pnginfo.add_text('s_tag', str(seed))
            params.update(pnginfo=pnginfo)
            
            super().save(fp, format=self.format, **params)
            
            self.paste(back_img)

    def open(fp, *args, **kwargs):
        image = super_open(fp, *args, **kwargs)
        pnginfo = image.info or {}
        if 's_tag' in pnginfo:
            try:
                seed = int(pnginfo['s_tag'])
                decrypted = process_image(image, seed)
                
                pnginfo_clean = image.info.copy()
                del pnginfo_clean['s_tag']
                
                decrypted.info = pnginfo_clean
                image = AntiSeekImage.from_image(image=decrypted)
                image._is_decrypted = True
                return image
            except:
                pass
        return AntiSeekImage.from_image(image=image)
    
    def encode_pil_to_base64(image: PILImage.Image):
        with io.BytesIO() as output_bytes:
            pnginfo = image.info or {}
            
            if 's_tag' in pnginfo:
                try:
                    seed = int(pnginfo['s_tag'])
                    image = process_image(image, seed)
                except: pass
            
            target_format = getattr(shared.opts, 'antiseek_preview_format', 'png').lower()
            target_quality = int(getattr(shared.opts, 'antiseek_preview_quality', 90))

            if target_format == 'jpeg':
                if image.mode in ('RGBA', 'LA'):
                    image = image.convert('RGB')
                image.save(output_bytes, format="JPEG", quality=target_quality)
            elif target_format == 'webp':
                save_args = {"quality": target_quality}
                if target_quality >= 100:
                    save_args['lossless'] = True
                image.save(output_bytes, format="WEBP", **save_args)
            elif target_format == 'avif':
                image.save(output_bytes, format="AVIF", quality=target_quality)
            else:
                image.save(output_bytes, format="PNG", quality=opts.jpeg_quality)
            
            bytes_data = output_bytes.getvalue()
        return base64.b64encode(bytes_data)

    if piexif:
        _original_piexif_insert = piexif.insert
        
        def _antiseek_piexif_insert(exif, image, **kwargs):
            try:
                _original_piexif_insert(exif, image, **kwargs)
            except piexif.InvalidImageDataError:
                pass
            except Exception:
                raise

        piexif.insert = _antiseek_piexif_insert
  
    PILImage.Image = AntiSeekImage
    PILImage.open = open
    api.encode_pil_to_base64 = encode_pil_to_base64

script_callbacks.on_ui_settings(on_ui_settings)
script_callbacks.on_app_started(app_started_callback)
print('Anti-Seek Plugin Active! 图像潜影插件启用！')