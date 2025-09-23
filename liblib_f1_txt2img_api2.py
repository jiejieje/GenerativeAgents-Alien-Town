import requests
import time
import hashlib
import json
import os
# from PIL import Image # 文生图不需要直接处理本地图片尺寸，除非用于其他目的
# from urllib.parse import urlparse # 同上
import hmac
from datetime import datetime
import uuid
import base64
import io # 仍然需要io.BytesIO来处理下载的图片数据
import argparse # 新增导入

# --- 常量定义 ---
# 可由配置覆盖
LIBLIBAI_BASE_URL = "https://openapi.liblibai.cloud" # LiblibAI API 基础 URL
F1_DEV_FP8_CHECKPOINT_ID = "412b427ddb674b4dbab9e5abd5ae6057" # F.1 模型 (F.1-dev-fp8) 的检查点ID
DEFAULT_POLL_INTERVAL = 5 # 查询任务状态的默认轮询间隔时间（秒）
DEFAULT_REQUEST_TIMEOUT = 30 # API请求的默认超时时间（秒）
DEFAULT_TASK_TIMEOUT = 300 # 整个生图任务（包括轮询）的默认超时时间（秒）

# 文生图特定的默认参数常量
DEFAULT_TXT2IMG_PROMPT = ""
DEFAULT_TXT2IMG_NEGATIVE_PROMPT = "ugly, blurry, watermark, text, deformed, worst quality, low quality, jpeg artifacts"
DEFAULT_TXT2IMG_WIDTH = 512# F.1模型推荐尺寸
DEFAULT_TXT2IMG_HEIGHT = 512 #   F.1模型推荐尺寸

DEFAULT_TXT2IMG_STEPS = 20

DEFAULT_TXT2IMG_CFG_SCALE = 3.5
DEFAULT_TXT2IMG_SAMPLER_NAME = "Euler a"
DEFAULT_TXT2IMG_IMG_COUNT = 1

# 新增：预设提示词字典
PRESET_PROMPTS = {
    "插画风格": "illustration, drawing, painting, artwork, digital art, 4k, high quality",

}

# JSON 文件相关常量
SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__)) # 获取脚本文件所在的真实目录
DEFAULT_JSON_RECORDS_DIR = os.path.join(SCRIPT_DIR, "results", "paint-records") # 默认JSON记录目录，相对于脚本文件
DEFAULT_JSON_FILENAME_STEM = "sim_20250520_165956" # 默认JSON文件名 (不含.json后缀)

class LiblibF1Txt2ImgAPI:
    """
    LiblibAI F.1 模型文生图 API 客户端。
    使用 /api/generate/webui/text2img 接口进行文生图。
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
            _txt2img_cfg = _f1_cfg.get("txt2img", {}) if isinstance(_f1_cfg, dict) else {}
            if isinstance(_txt2img_cfg, dict):
                globals()["F1_DEV_FP8_CHECKPOINT_ID"] = _txt2img_cfg.get("checkpoint_id", F1_DEV_FP8_CHECKPOINT_ID)

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
        data_to_sign = f"{api_path}&{timestamp_ms}&{signature_nonce}"
        hashed_signature = self._hmac_sha1_encode(self.secret_key, data_to_sign)
        signature = base64.urlsafe_b64encode(hashed_signature).rstrip(b'=').decode('utf-8')
        return signature

    def _build_request_url(self, api_path: str) -> str:
        """构建带有认证参数的完整API请求URL。"""
        timestamp_ms, signature_nonce = self._generate_signature_params()
        signature = self._calculate_signature(api_path, timestamp_ms, signature_nonce)
        request_url = (
            f"{self.base_url}{api_path}?"
            f"AccessKey={self.access_key}&"
            f"Signature={signature}&"
            f"Timestamp={timestamp_ms}&"
            f"SignatureNonce={signature_nonce}"
        )
        return request_url

    # 文生图不需要 _get_image_dimensions_from_url 方法

    def submit_txt2img_task(self, generate_params: dict, template_uuid: str = None) -> dict | None:
        """
        提交文生图任务到 /api/generate/webui/text2img。
        :param generate_params: 文生图的核心参数字典。
        :param template_uuid: (可选) 参数模板的UUID。
        :return: API响应的JSON数据字典，或在失败时返回None。
        """
        api_path = "/api/generate/webui/text2img" # 端点修改为文生图
        request_url = self._build_request_url(api_path)

        payload = {"generateParams": generate_params}
        if template_uuid:
            payload["templateUuid"] = template_uuid

        print(f"\n[API请求] 提交文生图任务到: {request_url}")
        print(f"[API请求] 请求体: {json.dumps(payload, indent=4, ensure_ascii=False)}")

        try:
            response = requests.post(request_url, headers=self.common_headers, json=payload, timeout=DEFAULT_REQUEST_TIMEOUT)
            response.raise_for_status()
            result = response.json()
            print(f"[API响应] 提交任务: {json.dumps(result, indent=4, ensure_ascii=False)}")
            if result.get("code") != 0:
                print(f"提交任务业务失败: Code={result.get('code')}, Msg={result.get('msg')}")
            return result
        except requests.exceptions.HTTPError as e:
            print(f"提交文生图任务时发生HTTP错误: {e}")
            print(f"响应内容: {e.response.text}")
        except requests.exceptions.RequestException as e:
            print(f"提交文生图任务时发生网络错误: {e}")
        except json.JSONDecodeError as e:
            print(f"解析提交任务响应JSON时发生错误: {e}. 响应文本: {response.text if 'response' in locals() else 'N/A'}")
        return None

    def query_task_status(self, generate_uuid: str) -> dict | None:
        """查询指定任务UUID的生成状态和结果 (此方法与图生图通用)。"""
        api_path = "/api/generate/webui/status"
        request_url = self._build_request_url(api_path)
        payload = {"generateUuid": generate_uuid}
        print(f"\n[API请求] 查询任务状态 (UUID: {generate_uuid}) 到: {request_url}")
        try:
            response = requests.post(request_url, headers=self.common_headers, json=payload, timeout=DEFAULT_REQUEST_TIMEOUT)
            response.raise_for_status()
            result = response.json()
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
        """下载图片并保存到指定路径 (此方法与图生图通用)。"""
        try:
            print(f"正在下载图片: {image_url} 到 {save_path}")
            response = requests.get(image_url, stream=True, timeout=DEFAULT_REQUEST_TIMEOUT * 2)
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

    def generate_f1_text_to_image(
        self,
        prompt: str = DEFAULT_TXT2IMG_PROMPT,
        negative_prompt: str = DEFAULT_TXT2IMG_NEGATIVE_PROMPT,
        width: int = DEFAULT_TXT2IMG_WIDTH,
        height: int = DEFAULT_TXT2IMG_HEIGHT,
        sampler_name: str = DEFAULT_TXT2IMG_SAMPLER_NAME,
        steps: int = DEFAULT_TXT2IMG_STEPS,
        cfg_scale: float = DEFAULT_TXT2IMG_CFG_SCALE,
        seed: int = -1,
        img_count: int = DEFAULT_TXT2IMG_IMG_COUNT,
        face_fix: bool = False, # API可能用 "restoreFaces": 0/1
        additional_network: list = None, # 例如 LoRA: [{"modelId": "uuid", "weight": 0.8}]
        save_dir: str = "f1_txt2img_results", # 文生图的默认保存目录
        task_timeout: int = DEFAULT_TASK_TIMEOUT,
        record_timestamp_for_filename: str = None, # 新增参数，用于自定义文件名
        preset_style_key: str = None # 新增参数，用于指定预设风格的键
    ) -> dict | None:
        """
        使用F.1模型进行文生图的核心方法。
        处理任务提交、状态轮询，并在成功后下载和保存图片。
        """
        
        # 0. 处理预设提示词
        final_prompt = prompt
        if preset_style_key and preset_style_key in PRESET_PROMPTS:
            preset_text = PRESET_PROMPTS[preset_style_key]
            if final_prompt: # 如果用户输入了prompt，则用逗号拼接
                final_prompt = f"{preset_text}, {final_prompt}"
            else: # 如果用户没有输入prompt，则直接使用预设
                final_prompt = preset_text
            print(f"已应用预设风格 '{preset_style_key}': {preset_text}")
        elif preset_style_key:
            print(f"警告: 预设风格键 '{preset_style_key}' 未在 PRESET_PROMPTS 中找到，将仅使用原始prompt。")


        # 1. 构建文生图参数 (generateParams)
        txt2img_params = {
            "checkPointId": F1_DEV_FP8_CHECKPOINT_ID,
            "prompt": final_prompt, # 使用处理后的 final_prompt
            "negativePrompt": negative_prompt,
            "width": width,
            "height": height,
            "samplerName": sampler_name,
            "steps": steps,
            "cfgScale": cfg_scale,
            "seed": seed,
            "imgCount": img_count,
            "randnSource": 0, # 随机种子来源，0通常是CPU
            "restoreFaces": 1 if face_fix else 0,
        }
        if additional_network:
            txt2img_params["additionalNetwork"] = additional_network
        
        # 2. 提交文生图任务
        submission_response = self.submit_txt2img_task(generate_params=txt2img_params)

        if not submission_response or submission_response.get("code") != 0:
            print("文生图任务提交失败或API返回错误。")
            return submission_response

        task_data = submission_response.get("data")
        if not task_data or "generateUuid" not in task_data:
            print("提交响应中未找到 'data' 或 'generateUuid'。")
            return submission_response

        generate_uuid = task_data["generateUuid"]
        print(f"文生图任务已提交，任务UUID: {generate_uuid}")

        # 3. 轮询任务状态直到完成或超时
        start_time = time.time()
        final_status_response = None

        while True:
            current_time = time.time()
            if (current_time - start_time) > task_timeout:
                print(f"任务 {generate_uuid} 等待超时 ({task_timeout}秒)，已退出轮询。")
                final_status_response = self.query_task_status(generate_uuid)
                if final_status_response and final_status_response.get("data", {}).get("generateStatus") == 5:
                     print("超时前任务已完成，但可能未处理图片下载。")
                else:
                    return {"code": -1, "msg": "任务超时", "data": {"generateUuid": generate_uuid}}
            
            status_response = self.query_task_status(generate_uuid)
            final_status_response = status_response

            if not status_response:
                print(f"查询任务 {generate_uuid} 状态失败，终止轮询。")
                return None

            if status_response.get("code") != 0:
                print(f"查询任务 {generate_uuid} 状态API返回错误: {status_response.get('msg')}")
                return status_response

            task_status_data = status_response.get("data", {})
            generate_status = task_status_data.get("generateStatus")
            generate_msg = task_status_data.get("generateMsg", "无消息")
            print(f"任务 {generate_uuid} 状态: {generate_status} ({generate_msg}), 等待 {self.poll_interval} 秒...")

            if generate_status == 5: # 任务成功
                print(f"任务 {generate_uuid} 成功完成！")
                images = task_status_data.get("images", [])
                if images and isinstance(images, list) and len(images) > 0:
                    try:
                        os.makedirs(save_dir, exist_ok=True)
                    except OSError as e:
                        print(f"创建保存目录 {save_dir} 失败: {e}. 图片将不会被保存。")
                        return final_status_response

                    for i, image_info in enumerate(images):
                        if image_info and isinstance(image_info, dict) and image_info.get("imageUrl"):
                            image_url = image_info["imageUrl"]
                            image_seed = image_info.get("seed", "unknown")
                            base_url_path = image_url.split('?')[0]
                            file_extension = os.path.splitext(os.path.basename(base_url_path))[-1]
                            if not file_extension or len(file_extension) > 5 or len(file_extension) < 2:
                                file_extension = ".png"

                            if record_timestamp_for_filename:
                                base_name_part = record_timestamp_for_filename
                            else:
                                # 如果未提供记录时间戳，则退回到旧的基于当前时间和种子的命名方式
                                current_time_str = datetime.now().strftime("%Y%m%d_%H%M%S")
                                base_name_part = f"f1_txt2img_{current_time_str}_seed_{image_seed}"

                            if img_count > 1:
                                filename = f"{base_name_part}_idx_{i}{file_extension}"
                            else:
                                filename = f"{base_name_part}{file_extension}"
                            
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
        return final_status_response

# --- 主函数示例 ---
if __name__ == '__main__':
    print("--- LiblibAI F.1 文生图 API 脚本 (已更新提示词和路径逻辑) ---")

    # --- 新增：解析命令行参数 ---
    parser = argparse.ArgumentParser(description="LiblibAI F.1 文生图 API 脚本")
    parser.add_argument("--sim_name", type=str, help="指定模拟名称作为JSON文件的词干 (例如 'sim_xxxxxx')")
    args = parser.parse_args()
    # --- 结束：解析命令行参数 ---

    # 从环境变量或配置读取凭据
    try:
        _script_dir = os.path.dirname(os.path.realpath(__file__))
        with open(os.path.join(_script_dir, "data", "config.json"), "r", encoding="utf-8") as _cfgf2:
            _cfg2 = json.load(_cfgf2)
    except Exception:
        _cfg2 = {}
    _libcfg2 = (_cfg2.get("services", {}).get("liblibai", {}) if isinstance(_cfg2, dict) else {})
    YOUR_ACCESS_KEY = os.getenv("LIBLIBAI_ACCESS_KEY") or _libcfg2.get("access_key", "")
    YOUR_SECRET_KEY = os.getenv("LIBLIBAI_SECRET_KEY") or _libcfg2.get("secret_key", "")

    # --- 配置区域 ---
    # 使用在文件顶部定义的常量作为默认值
    # 您仍然可以在这里按需覆盖它们，例如：
    # JSON_RECORDS_DIR_TO_USE = "some_other_path/results/paint-records"
    # JSON_FILENAME_STEM_TO_USE = "another_file"

    JSON_RECORDS_DIR_TO_USE = DEFAULT_JSON_RECORDS_DIR
    
    # 根据命令行参数或默认值设置JSON文件名
    if args.sim_name:
        JSON_FILENAME_STEM_TO_USE = args.sim_name
        print(f"已从命令行参数接收到模拟名称，将使用 '{JSON_FILENAME_STEM_TO_USE}' 作为JSON文件名。")
    else:
        JSON_FILENAME_STEM_TO_USE = DEFAULT_JSON_FILENAME_STEM
        print(f"未从命令行参数接收到模拟名称，将使用默认值 '{DEFAULT_JSON_FILENAME_STEM}' 作为JSON文件名。")


    # 图片保存的基础目录 (相对于项目根目录)
    # 当此脚本被 AI小镇启动器.py 调用时，其 cwd (当前工作目录) 会被设置为 generative_agents 目录。
    # 因此，此处的路径应相对于 generative_agents 目录。
    BASE_OUTPUT_DIR = os.path.join("frontend", "static", "generated_images")
    # --- 结束配置区域 ---


    if not YOUR_ACCESS_KEY or not YOUR_SECRET_KEY: # 缺失检查
        print("\n警告: 未提供 LiblibAI AccessKey/SecretKey。")
        print("请通过环境变量 LIBLIBAI_ACCESS_KEY / LIBLIBAI_SECRET_KEY 或 config.services.liblibai.* 配置。")
    else:
        try:
            client = LiblibF1Txt2ImgAPI(access_key=YOUR_ACCESS_KEY, secret_key=YOUR_SECRET_KEY)
            
            json_file_path = os.path.join(JSON_RECORDS_DIR_TO_USE, f"{JSON_FILENAME_STEM_TO_USE}.json")
            
            print(f"\n尝试从以下路径加载绘画记录: {json_file_path}")

            if not os.path.exists(json_file_path):
                print(f"错误: JSON文件未找到路径 {json_file_path}")
                paint_records = []
            else:
                try:
                    with open(json_file_path, "r", encoding="utf-8") as f:
                        paint_records = json.load(f)
                    print(f"成功从 {JSON_FILENAME_STEM_TO_USE}.json 加载 {len(paint_records)} 条记录。")
                except json.JSONDecodeError:
                    print(f"错误: JSON文件 {json_file_path} 格式错误。")
                    paint_records = []
                except Exception as e:
                    print(f"读取JSON文件 {json_file_path} 时发生错误: {e}")
                    paint_records = []

            if not paint_records:
                print("没有可处理的绘画记录。脚本将退出。")
            else:
                for record_idx, record in enumerate(paint_records):
                    prompt_text = record.get("绘画内容")
                    agent_name = record.get("智能体")
                    timestamp_from_json = record.get("时间", f"record_{record_idx}") # 获取时间或使用索引作为标识

                    if not prompt_text or not agent_name:
                        print(f"记录 {record_idx + 1} (标识: {timestamp_from_json}) 缺少 '绘画内容' 或 '智能体'，已跳过。")
                        continue

                    print(f"\n--- 处理记录 {record_idx + 1}/{len(paint_records)} ---")
                    print(f"  智能体: {agent_name}")
                    print(f"  原始记录标识: {timestamp_from_json}")
                    print(f"  提示词: {prompt_text}")

                    # 清理agent_name以便安全地用作路径的一部分
                    cleaned_agent_name = "".join(c if c.isalnum() or c in (' ', '_', '-') else '_' for c in agent_name).rstrip()
                    cleaned_agent_name = cleaned_agent_name.replace(' ', '_')
                    
                    # 构建特定于此任务的保存目录
                    # 结构: BASE_OUTPUT_DIR / JSON_FILENAME_STEM_TO_USE / cleaned_agent_name /
                    current_save_dir = os.path.join(BASE_OUTPUT_DIR, JSON_FILENAME_STEM_TO_USE, cleaned_agent_name)
                    
                    # 确保目录存在 (generate_f1_text_to_image 内部也会尝试创建, 但这里提前打日志更清晰)
                    if not os.path.exists(current_save_dir):
                        try:
                            os.makedirs(current_save_dir, exist_ok=True)
                            print(f"  已创建图片保存目录: {current_save_dir}")
                        except OSError as e:
                            print(f"  创建目录 {current_save_dir} 失败: {e}。将尝试在API方法中创建。")
                    else:
                        print(f"  图片将保存到现有目录: {current_save_dir}")


                    # Negative prompt 可以使用默认值，或者如果JSON记录中也包含相关字段，则可以从那里加载
                    negative_prompt_text = DEFAULT_TXT2IMG_NEGATIVE_PROMPT 
                    
                    # 清理时间戳用于文件名
                    cleaned_timestamp_for_filename = timestamp_from_json.replace(':', '').replace(' ', '_')

                    # 调用API
                    result = client.generate_f1_text_to_image(
                        prompt=prompt_text,
                        negative_prompt=negative_prompt_text,
                        # 使用类中定义的默认宽高、steps等 (这些是方法签名的默认值)
                        # width=1024,    # 若要覆盖默认值，取消注释并设置
                        # height=768,    # 同上
                        # steps=30,      # 同上
                        # cfg_scale=7.5, # 同上
                        seed=-1,       # 随机种子
                        img_count=DEFAULT_TXT2IMG_IMG_COUNT, # 使用默认值 (1)
                        save_dir=current_save_dir, # 传递构建好的完整保存路径
                        record_timestamp_for_filename=cleaned_timestamp_for_filename, # 传递清理后的时间戳作为文件名基础
                        preset_style_key="插画风格", # 新增：演示使用预设风格，可以设置为 None 或其他键
                        # task_timeout=360 # 若要覆盖默认值，取消注释并设置
                    )

                    if result:
                        print(f"\n--- 记录 {record_idx + 1} ({agent_name}) 文生图任务最终结果 ---")
                        status_code = result.get("code")
                        status_msg = result.get("msg")
                        generate_status = result.get("data", {}).get("generateStatus")
                        print(f"  API Code: {status_code}, Message: {status_msg}, Task Status: {generate_status}")

                        if status_code == 0 and generate_status == 5:
                            print(f"  图片已为智能体 '{agent_name}' 生成 (提示词: '{prompt_text[:50]}...')。")
                            print(f"  请检查 '{current_save_dir}' 目录。")
                        elif status_code == -1 and "超时" in (status_msg or ""):
                            print(f"  任务超时。智能体: '{agent_name}', 提示词: '{prompt_text[:50]}...'")
                        else:
                            print(f"  文生图任务未完全成功或API返回错误。智能体: '{agent_name}'")
                            task_data = result.get('data', {})
                            print(f"  Task Data Status: {task_data.get('generateStatus')}, Task Message: {task_data.get('generateMsg')}")
                    else:
                        print(f"  API调用失败，没有返回结果。智能体: '{agent_name}'")
                    
                    print(f"--- 完成处理记录 {record_idx + 1} ({agent_name}) ---")
                
                print("\n所有记录处理完毕。")

        except ValueError as ve:
            print(f"初始化错误: {ve}")
        except Exception as e:
            print(f"执行过程中发生意外错误: {e}")
            import traceback
            traceback.print_exc() # 打印详细的错误堆栈

    print("\n--- 脚本执行完毕 ---") 