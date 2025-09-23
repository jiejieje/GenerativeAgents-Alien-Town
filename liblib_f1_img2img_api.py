import requests
import time
import hashlib
import json
import os
from PIL import Image
from urllib.parse import urlparse
import hmac
from datetime import datetime
import uuid
import base64
import io

# --- 常量定义 ---
# LiblibAI API基础URL（可由配置覆盖）
LIBLIBAI_BASE_URL = "https://openapi.liblibai.cloud" # LiblibAI API 基础 URL
# F.1 模型 (F.1-dev-fp8) 的 Checkpoint ID（可由配置覆盖）
F1_DEV_FP8_CHECKPOINT_ID = "412b427ddb674b4dbab9e5abd5ae6057" # F.1 模型 (F.1-dev-fp8) 的检查点ID
# 默认轮询间隔时间（秒）
DEFAULT_POLL_INTERVAL = 5 # 查询任务状态的默认轮询间隔时间（秒）
# 默认请求超时时间（秒）
DEFAULT_REQUEST_TIMEOUT = 30 # API请求的默认超时时间（秒）
# 默认任务处理超时时间（秒）
DEFAULT_TASK_TIMEOUT = 300 # 整个生图任务（包括轮询）的默认超时时间（秒）

# 新增的默认参数常量
DEFAULT_SOURCE_IMAGE_URL_PLACEHOLDER = "https://liblibai-online.liblib.cloud/sd-gen-save-img/439156888-85befbbf26edb6b0897bf7871ff2958e94d8a59b94629c8b711ebe01dce8fc0a.png?Token=c28c11428bb140978579f5e2c5884fc1&image_process=format,webp&x-oss-process=image/resize,w_280,m_lfit/format,webp" 
# 默认源图片URL占位符 (实际使用时应被具体URL替换) - 用户已更新为实际URL
DEFAULT_DENOISING_STRENGTH = 0.45
# 默认重绘幅度 (控制AI修改原图的程度) - 用户已更新
DEFAULT_CFG_SCALE = 3.5
 # 默认CFG Scale (提示词相关性引导系数)
DEFAULT_IMG_COUNT = 1
# 默认生成图片数量
DEFAULT_PROMPT_PLACEHOLDER = "top down game room"
 # 默认正向提示词占位符
DEFAULT_NEGATIVE_PROMPT = "ugly, blurry, watermark, text, deformed, worst quality, low quality, jpeg artifacts"
 # 默认负向提示词 - 已修正格式
DEFAULT_STEPS = 20
 # 默认采样步数
DEFAULT_RESIZE_MODE = 1 
# 默认图片调整模式 (0:仅调整大小,不保持宽高比)
DEFAULT_SAMPLER_NAME = "Euler a" 
# 默认采样器名称

class LiblibF1Img2ImgAPI:
    """
    LiblibAI F.1 模型图生图 API 客户端。
    使用 /api/generate/webui/img2img 接口进行图生图。
    签名信息通过URL查询参数传递。
    """

    def __init__(self, access_key: str, secret_key: str, poll_interval: int = DEFAULT_POLL_INTERVAL):
        """
        初始化API客户端。

        :param access_key: 您的 LiblibAI AccessKey ID。
        :param secret_key: 您的 LiblibAI Secret Access Key。
        :param poll_interval: 查询任务状态的轮询间隔时间（秒）。
        """
        if not access_key or not secret_key:
            raise ValueError("AccessKey 和 SecretKey 不能为空。")
        
        self.access_key = access_key
        self.secret_key = secret_key
        self.poll_interval = poll_interval
        self.base_url = LIBLIBAI_BASE_URL
        self.common_headers = {'Content-Type': 'application/json'}

        # 读取配置覆盖 base_url 与 checkpoint（如果存在）
        try:
            script_dir = os.path.dirname(os.path.realpath(__file__))
            with open(os.path.join(script_dir, "data", "config.json"), "r", encoding="utf-8") as _cfgf:
                _cfg = json.load(_cfgf)
        except Exception:
            _cfg = {}
        _libcfg = (_cfg.get("services", {}).get("liblibai", {}) if isinstance(_cfg, dict) else {})
        if isinstance(_libcfg, dict):
            self.base_url = os.getenv("LIBLIBAI_BASE_URL") or _libcfg.get("base_url", self.base_url)
            _f1_cfg = _libcfg.get("f1", {}) if isinstance(_libcfg, dict) else {}
            _img2img_cfg = _f1_cfg.get("img2img", {}) if isinstance(_f1_cfg, dict) else {}
            if isinstance(_img2img_cfg, dict):
                globals()["F1_DEV_FP8_CHECKPOINT_ID"] = _img2img_cfg.get("checkpoint_id", F1_DEV_FP8_CHECKPOINT_ID)

    def _generate_signature_params(self) -> tuple[int, str]:
        """生成签名所需的时间戳和随机字符串(nonce)。"""
        timestamp_ms = int(datetime.now().timestamp() * 1000)
        signature_nonce = str(uuid.uuid1())
        return timestamp_ms, signature_nonce

    def _hmac_sha1_encode(self, key: str, data: str) -> bytes:
        """使用HMAC-SHA1算法对数据进行加密。"""
        hmac_code = hmac.new(key.encode('utf-8'), data.encode('utf-8'), hashlib.sha1)
        return hmac_code.digest()

    def _calculate_signature(self, api_path: str, timestamp_ms: int, signature_nonce: str) -> str:
        """计算API请求的签名。"""
        # 根据文档，签名字符串格式为: api_path + "&" + timestamp + "&" + nonce
        data_to_sign = f"{api_path}&{timestamp_ms}&{signature_nonce}"
        hashed_signature = self._hmac_sha1_encode(self.secret_key, data_to_sign)
        # 使用URL安全的Base64编码，并移除末尾的等号
        signature = base64.urlsafe_b64encode(hashed_signature).rstrip(b'=').decode('utf-8')
        return signature

    def _build_request_url(self, api_path: str) -> str:
        """构建带有认证参数的完整API请求URL。"""
        timestamp_ms, signature_nonce = self._generate_signature_params()
        signature = self._calculate_signature(api_path, timestamp_ms, signature_nonce)
        
        # 构建包含认证参数的URL
        request_url = (
            f"{self.base_url}{api_path}?"
            f"AccessKey={self.access_key}&"
            f"Signature={signature}&"
            f"Timestamp={timestamp_ms}&"
            f"SignatureNonce={signature_nonce}"
        )
        return request_url

    def _get_image_dimensions_from_url(self, image_url: str, timeout: int = DEFAULT_REQUEST_TIMEOUT) -> tuple[int | None, int | None]:
        """
        从给定的URL下载图片并获取其原始宽高。

        :param image_url: 图片的公开URL。
        :param timeout: 请求超时时间。
        :return: (宽度, 高度) 元组，如果获取失败则为 (None, None)。
        """
        try:
            print(f"正在从URL获取源图片尺寸: {image_url}")
            response = requests.get(image_url, timeout=timeout, stream=True)
            response.raise_for_status()
            img = Image.open(io.BytesIO(response.content))
            width, height = img.size
            if width > 0 and height > 0:
                print(f"成功获取源图片尺寸: 宽={width}, 高={height}")
                return width, height
            else:
                print("未能获取有效的源图片尺寸（宽或高为0）。")
                return None, None
        except requests.exceptions.RequestException as e:
            print(f"从URL获取源图片失败 (RequestException): {e}")
        except IOError as e: # PIL.UnidentifiedImageError 是 IOError 的子类
            print(f"无法打开源图片或读取尺寸 (IOError/UnidentifiedImageError): {e}")
        except Exception as e:
            print(f"获取源图片尺寸时发生未知错误: {e}")
        return None, None

    def submit_img2img_task(self, generate_params: dict, template_uuid: str = None) -> dict | None:
        """
        提交图生图任务到 /api/generate/webui/img2img。

        :param generate_params: 图生图的核心参数字典。
        :param template_uuid: (可选) 参数模板的UUID。
        :return: API响应的JSON数据字典，或在失败时返回None。
        """
        api_path = "/api/generate/webui/img2img"
        request_url = self._build_request_url(api_path)

        payload = {"generateParams": generate_params}
        if template_uuid:
            payload["templateUuid"] = template_uuid

        print(f"\n[API请求] 提交图生图任务到: {request_url}")
        print(f"[API请求] 请求体: {json.dumps(payload, indent=4, ensure_ascii=False)}")

        try:
            response = requests.post(request_url, headers=self.common_headers, json=payload, timeout=DEFAULT_REQUEST_TIMEOUT)
            response.raise_for_status()  # 如果HTTP状态码是4xx或5xx，则抛出HTTPError
            result = response.json()
            print(f"[API响应] 提交任务: {json.dumps(result, indent=4, ensure_ascii=False)}")
            if result.get("code") != 0:
                print(f"提交任务业务失败: Code={result.get('code')}, Msg={result.get('msg')}")
            return result
        except requests.exceptions.HTTPError as e:
            print(f"提交图生图任务时发生HTTP错误: {e}")
            print(f"响应内容: {e.response.text}")
        except requests.exceptions.RequestException as e:
            print(f"提交图生图任务时发生网络错误: {e}")
        except json.JSONDecodeError as e:
            print(f"解析提交任务响应JSON时发生错误: {e}. 响应文本: {response.text if 'response' in locals() else 'N/A'}")
        return None

    def query_task_status(self, generate_uuid: str) -> dict | None:
        """
        查询指定任务UUID的生成状态和结果。
        接口: /api/generate/webui/status

        :param generate_uuid: 任务的UUID。
        :return: API响应的JSON数据字典，或在失败时返回None。
        """
        api_path = "/api/generate/webui/status"
        request_url = self._build_request_url(api_path)
        payload = {"generateUuid": generate_uuid}

        print(f"\n[API请求] 查询任务状态 (UUID: {generate_uuid}) 到: {request_url}")
        # print(f"[API请求] 请求体: {json.dumps(payload, indent=4, ensure_ascii=False)}") # 查询请求体较简单，可省略

        try:
            response = requests.post(request_url, headers=self.common_headers, json=payload, timeout=DEFAULT_REQUEST_TIMEOUT)
            response.raise_for_status()
            result = response.json()
            # print(f"[API响应] 查询状态: {json.dumps(result, indent=4, ensure_ascii=False)}") # 避免过多打印
            return result
        except requests.exceptions.HTTPError as e:
            print(f"查询任务状态时发生HTTP错误 (UUID: {generate_uuid}): {e}")
            print(f"响应内容: {e.response.text}")
        except requests.exceptions.RequestException as e:
            print(f"查询任务状态时发生网络错误 (UUID: {generate_uuid}): {e}")
        except json.JSONDecodeError as e:
            print(f"解析查询状态响应JSON时发生错误 (UUID: {generate_uuid}): {e}. 响应文本: {response.text if 'response' in locals() else 'N/A'}")
        return None
        
    def _download_image(self, image_url: str, save_path: str) -> bool:
        """下载图片并保存到指定路径。"""
        try:
            print(f"正在下载图片: {image_url} 到 {save_path}")
            response = requests.get(image_url, stream=True, timeout=DEFAULT_REQUEST_TIMEOUT * 2) # 下载允许更长时间
            response.raise_for_status()
            
            os.makedirs(os.path.dirname(save_path), exist_ok=True)

            with open(save_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            print(f"图片成功保存到: {save_path}")
            return True
        except requests.exceptions.RequestException as e:
            print(f"下载图片 {image_url} 失败: {e}")
        except IOError as e:
            print(f"保存图片到 {save_path} 时发生IO错误: {e}")
        except Exception as e:
            print(f"下载或保存图片时发生未知错误: {e}")
        return False

    def generate_f1_image(
        self,
        source_image_url: str,
        prompt: str,
        negative_prompt: str = DEFAULT_NEGATIVE_PROMPT,
        denoising_strength: float = DEFAULT_DENOISING_STRENGTH,
        sampler_name: str = DEFAULT_SAMPLER_NAME,
        steps: int = DEFAULT_STEPS,
        cfg_scale: float = DEFAULT_CFG_SCALE,
        seed: int = -1,
        output_width: int = None,
        output_height: int = None,
        default_dimension: int = 1024,
        resize_mode: int = DEFAULT_RESIZE_MODE,
        face_fix: bool = False,
        additional_network: list = None,
        img_count: int = DEFAULT_IMG_COUNT,
        save_dir: str = r"D:\AI repo\new generative agents\角色测试\3.30日完成了角色地图和引擎更换\哩布生成的图片",
        task_timeout: int = DEFAULT_TASK_TIMEOUT
    ) -> dict | None:
        """
        使用F.1模型进行图生图的核心方法。
        它会处理任务提交、状态轮询，并在成功后下载和保存图片。

        :param source_image_url: 源图片的公开URL。
        :param prompt: 正向提示词。
        :param negative_prompt: 负向提示词。
        :param denoising_strength: 重绘幅度 (0.0 to 1.0)。
        :param sampler_name: 采样器名称 (例如 "Euler a")。
        :param steps: 采样步数。
        :param cfg_scale: 提示词相关性。
        :param seed: 随机种子, -1 表示随机。
        :param output_width: 最终生成图片的宽度。如果为None，则尝试使用源图宽度，否则使用default_dimension。
        :param output_height: 最终生成图片的高度。如果为None，则尝试使用源图高度，否则使用default_dimension。
        :param default_dimension: 当无法获取源图尺寸且output_width/height未指定时的默认宽高。
        :param resize_mode: 图像调整模式。
        :param face_fix: 是否启用面部修复。
        :param additional_network: 额外的网络配置，如LoRA。
        :param img_count: 生成图片的数量。
        :param save_dir: 图片保存的目录。
        :param task_timeout: 整个任务（包括轮询）的超时时间（秒）。
        :return: 最终的任务状态API响应字典，或在失败/超时时返回None。
        """
        
        # 1. 准备源图片和尺寸
        base_source_url = source_image_url.split('?')[0]
        print(f"将使用基础源图片URL进行处理: {base_source_url}")

        actual_width, actual_height = output_width, output_height
        if actual_width is None or actual_height is None:
            source_w, source_h = self._get_image_dimensions_from_url(base_source_url)
            if actual_width is None:
                actual_width = source_w if source_w else default_dimension
            if actual_height is None:
                actual_height = source_h if source_h else default_dimension
            print(f"推断生成尺寸: 宽={actual_width}, 高={actual_height}")


        # 2. 构建图生图参数 (generateParams)
        # 注意：参数名称需严格对应LiblibAI文档中 /api/generate/webui/img2img 的要求
        img2img_params = {
            "checkPointId": F1_DEV_FP8_CHECKPOINT_ID, # 指定F.1模型
            "sourceImage": base_source_url,
            "prompt": prompt,
            "negativePrompt": negative_prompt,
            "denoisingStrength": denoising_strength,
            "samplerName": sampler_name, # API 可能接受 samplerName 或 sampler (ID)
            "steps": steps,
            "cfgScale": cfg_scale,
            "seed": seed,
            "width": actual_width,         # API可能需要原始的width/height参数
            "height": actual_height,       # 
            "resizedWidth": actual_width,  # 同时提供resizedWidth/Height确保尺寸控制
            "resizedHeight": actual_height,
            "resizeMode": resize_mode,
            "imgCount": img_count, # 使用传入或默认的图片数量
            "randnSource": 0, # 随机种子来源，0通常是CPU
            "restoreFaces": 1 if face_fix else 0, # API可能需要整数0或1
            # "faceFix": face_fix, # 或者直接用布尔值，取决于API具体实现
        }
        if additional_network: # 例如 [{"modelId": "lora_uuid", "weight": 0.7}]
            img2img_params["additionalNetwork"] = additional_network
        
        # 3. 提交图生图任务
        submission_response = self.submit_img2img_task(generate_params=img2img_params)

        if not submission_response or submission_response.get("code") != 0:
            print("图生图任务提交失败或API返回错误。")
            return submission_response # 返回提交时的错误信息

        task_data = submission_response.get("data")
        if not task_data or "generateUuid" not in task_data:
            print("提交响应中未找到 'data' 或 'generateUuid'。")
            return submission_response

        generate_uuid = task_data["generateUuid"]
        print(f"图生图任务已提交，任务UUID: {generate_uuid}")

        # 4. 轮询任务状态直到完成或超时
        start_time = time.time()
        final_status_response = None

        while True:
            current_time = time.time()
            if (current_time - start_time) > task_timeout:
                print(f"任务 {generate_uuid} 等待超时 ({task_timeout}秒)，已退出轮询。")
                # 尝试最后查询一次状态
                final_status_response = self.query_task_status(generate_uuid)
                if final_status_response and final_status_response.get("data", {}).get("generateStatus") == 5: # 5: 任务成功
                     print("超时前任务已完成，但可能未处理图片下载。")
                else:
                    return {"code": -1, "msg": "任务超时", "data": {"generateUuid": generate_uuid}}


            status_response = self.query_task_status(generate_uuid)
            final_status_response = status_response # 保存最新的状态

            if not status_response:
                print(f"查询任务 {generate_uuid} 状态失败，终止轮询。")
                return None # 查询失败

            if status_response.get("code") != 0:
                print(f"查询任务 {generate_uuid} 状态API返回错误: {status_response.get('msg')}")
                return status_response # API业务错误

            task_status_data = status_response.get("data", {})
            generate_status = task_status_data.get("generateStatus") # 1:等待, 2:执行中, 3:已生图(未审), 4:审核中, 5:任务成功, 6:任务失败
            generate_msg = task_status_data.get("generateMsg", "无消息")
            
            print(f"任务 {generate_uuid} 状态: {generate_status} ({generate_msg}), 等待 {self.poll_interval} 秒...")

            if generate_status == 5: # 任务成功
                print(f"任务 {generate_uuid} 成功完成！")
                images = task_status_data.get("images", [])
                if images and isinstance(images, list) and len(images) > 0:
                    # 确保保存目录存在
                    try:
                        os.makedirs(save_dir, exist_ok=True)
                    except OSError as e:
                        print(f"创建保存目录 {save_dir} 失败: {e}. 图片将不会被保存。")
                        return final_status_response # 返回结果，但不保存图片

                    for i, image_info in enumerate(images):
                        if image_info and isinstance(image_info, dict) and image_info.get("imageUrl"):
                            image_url = image_info["imageUrl"]
                            image_seed = image_info.get("seed", "unknown")
                            # 构建一个稍微独特的文件名
                            timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
                            base_url_path = image_url.split('?')[0]
                            file_extension = os.path.splitext(os.path.basename(base_url_path))[-1]
                            if not file_extension or len(file_extension) > 5 or len(file_extension) < 2:
                                file_extension = ".png" # 默认png
                            
                            filename = f"f1_img2img_{timestamp_str}_seed_{image_seed}_idx_{i}{file_extension}"
                            full_save_path = os.path.join(save_dir, filename)
                            self._download_image(image_url, full_save_path)
                        else:
                            print(f"图片 {i} 数据不完整或无imageUrl。")
                else:
                    print("任务成功，但响应中未找到有效的图片列表。")
                return final_status_response
            
            elif generate_status == 6: # 任务失败
                print(f"任务 {generate_uuid} 生成失败: {generate_msg}")
                return final_status_response

            time.sleep(self.poll_interval)
        
        return final_status_response # 理论上不应执行到这里，除非轮询逻辑有误

# --- 主函数示例 ---
if __name__ == '__main__':
    print("--- LiblibAI F.1 图生图 API 脚本 ---")

    # API 密钥：从环境变量或配置读取
    try:
        _script_dir = os.path.dirname(os.path.realpath(__file__))
        with open(os.path.join(_script_dir, "data", "config.json"), "r", encoding="utf-8") as _cfgf2:
            _cfg2 = json.load(_cfgf2)
    except Exception:
        _cfg2 = {}
    _libcfg2 = (_cfg2.get("services", {}).get("liblibai", {}) if isinstance(_cfg2, dict) else {})
    YOUR_ACCESS_KEY = os.getenv("LIBLIBAI_ACCESS_KEY") or _libcfg2.get("access_key", "")
    YOUR_SECRET_KEY = os.getenv("LIBLIBAI_SECRET_KEY") or _libcfg2.get("secret_key", "")

    # 检查是否缺失密钥
    if not YOUR_ACCESS_KEY or not YOUR_SECRET_KEY:
        print("\n警告: 未提供 LiblibAI AccessKey/SecretKey。")
        print("请通过环境变量 LIBLIBAI_ACCESS_KEY / LIBLIBAI_SECRET_KEY 或 config.services.liblibai.* 配置。")
    else:
        try:
            # 初始化API客户端
            client = LiblibF1Img2ImgAPI(access_key=YOUR_ACCESS_KEY, secret_key=YOUR_SECRET_KEY)

            # 使用常量或自定义值进行图生图参数示例
            # 源图片URL - 现在使用顶部定义的常量
            source_img_url = DEFAULT_SOURCE_IMAGE_URL_PLACEHOLDER
            # 提示词 - 使用常量占位符
            prompt_text = DEFAULT_PROMPT_PLACEHOLDER 
            
            # 其他参数可以从常量获取默认值，或在此处覆盖
            negative_prompt_text = DEFAULT_NEGATIVE_PROMPT # 使用常量
            denoising_strength_val = DEFAULT_DENOISING_STRENGTH # 使用常量
            steps_val = DEFAULT_STEPS # 使用常量
            cfg_scale_val = DEFAULT_CFG_SCALE # 使用常量
            img_count_val = DEFAULT_IMG_COUNT # 使用常量

            current_save_dir = r"D:\AI repo\new generative agents\角色测试\3.30日完成了角色地图和引擎更换\哩布生成的图片"
            
            print(f"\n准备调用 F.1 图生图 API...")
            print(f"源图片URL: {source_img_url}")
            print(f"提示词: {prompt_text}")
            print(f"使用默认重绘幅度: {denoising_strength_val}, CFG: {cfg_scale_val}, 步数: {steps_val}, 图片数量: {img_count_val}")

            result = client.generate_f1_image(
                source_image_url=source_img_url,
                prompt=prompt_text,
                negative_prompt=negative_prompt_text, 
                denoising_strength=denoising_strength_val, 
                steps=steps_val, 
                cfg_scale=cfg_scale_val, 
                seed=-1, # 修改为 -1 以便使用随机种子
                # output_width=768, # 注释掉，使用方法签名中的默认逻辑（源图尺寸或default_dimension）
                # output_height=768, # 注释掉，使用方法签名中的默认逻辑（源图尺寸或default_dimension）
                img_count=img_count_val, 
                save_dir=current_save_dir, 
                # task_timeout=360 # 注释掉，使用方法签名中的默认值 (DEFAULT_TASK_TIMEOUT)
            )

            if result:
                print("\n--- 图生图任务最终结果 ---")
                print(json.dumps(result, indent=4, ensure_ascii=False))
                
                if result.get("code") == 0 and result.get("data", {}).get("generateStatus") == 5:
                    print(f"\n图片已生成 (并尝试保存)。请检查 '{current_save_dir}' 目录。") # 使用变量动态显示路径
                elif result.get("code") == -1 and "超时" in result.get("msg", ""):
                     print("\n任务超时。")
                else:
                    print("\n图生图任务未完全成功或API返回错误。")
                    print(f"API Code: {result.get('code')}, Message: {result.get('msg')}")
                    task_data = result.get('data', {})
                    print(f"Task Status: {task_data.get('generateStatus')}, Task Message: {task_data.get('generateMsg')}")

        except ValueError as ve:
            print(f"初始化错误: {ve}")
        except Exception as e:
            print(f"执行过程中发生意外错误: {e}")

    print("\n--- 脚本执行完毕 ---") 