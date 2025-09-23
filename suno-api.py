import os
import sys
import requests
import json
import time # 导入 time 模块用于等待和轮询
import argparse # 新增导入

# 统一 UTF-8 编码，避免中文日志乱码
try:
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    os.environ.setdefault("PYTHONUTF8", "1")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# 冻结环境下的资源定位（与其他脚本保持一致）
def _get_base_dir():
    if getattr(sys, "frozen", False):
        try:
            return os.path.dirname(sys.executable)
        except Exception:
            pass
    return os.path.dirname(os.path.abspath(__file__))


def _get_resource_root(base_dir: str) -> str:
    candidates = [
        base_dir,
        os.path.join(base_dir, "_internal"),
        os.path.join(base_dir, "AI-Town"),
        os.path.join(base_dir, "AI-Town", "_internal"),
        os.path.join(os.path.dirname(base_dir), "_internal"),
        os.path.join(os.path.dirname(base_dir), "AI-Town", "_internal"),
    ]
    for root in candidates:
        if os.path.isdir(os.path.join(root, "frontend", "static")) and os.path.isdir(os.path.join(root, "data")):
            return root
    return base_dir


BASE_DIR = _get_base_dir()
RESOURCE_ROOT = _get_resource_root(BASE_DIR)

# 统一解析 results 目录（兼容开发与打包后运行）
def _resolve_records_dir(subdir: str) -> str:
    """返回首个存在的 results 子目录；如都不存在，返回首选并尽量创建。
    优先顺序：
    0) $GA_RESULTS_DIR/<subdir> （启动器注入，最高优先）
    1) BASE_DIR/results/<subdir>
    2) RESOURCE_ROOT/results/<subdir>
    3) dirname(RESOURCE_ROOT)/results/<subdir>
    """
    try:
        ga_results_root = os.getenv("GA_RESULTS_DIR")
        if ga_results_root:
            p = os.path.join(ga_results_root, subdir)
            if os.path.isdir(p):
                return p
            os.makedirs(p, exist_ok=True)
            return p
    except Exception:
        pass
    candidates = [
        os.path.join(BASE_DIR, "results", subdir),
        os.path.join(RESOURCE_ROOT, "results", subdir),
        os.path.join(os.path.dirname(RESOURCE_ROOT), "results", subdir),
    ]
    for d in candidates:
        try:
            if os.path.isdir(d):
                return d
        except Exception:
            pass
    try:
        os.makedirs(candidates[0], exist_ok=True)
    except Exception:
        pass
    return candidates[0]

# 从配置与环境变量获取 API 密钥与端点
SCRIPT_DIR = BASE_DIR # 获取脚本/可执行所在目录
try:
    with open(os.path.join(RESOURCE_ROOT, "data", "config.json"), "r", encoding="utf-8") as _cfgf:
        _cfg = json.load(_cfgf)
except Exception:
    _cfg = {}
_suno_cfg = (_cfg.get("services", {}).get("suno", {}) if isinstance(_cfg, dict) else {})

SUNO_API_KEY = os.getenv("SUNO_API_KEY") or _suno_cfg.get("api_key", "")

# Suno API 的基础 URL
BASE_URL = os.getenv("SUNO_BASE_URL") or _suno_cfg.get("base_url", "https://apibox.erweima.ai")

# --- 常量定义 ---
# JSON 文件相关常量（默认指向解析后的 results 路径）
DEFAULT_JSON_RECORDS_DIR = _resolve_records_dir("music-records")
DEFAULT_JSON_FILENAME_STEM = "sim_20250531_015225" # 默认JSON文件名 (不含.json后缀)

# 保存音乐的基础目标文件夹名称 (相对于脚本所在的 generative_agents 目录)
# 将结合 JSON_FILENAME_STEM 和 agent_name 创建子目录
BASE_SAVE_DIR_NAME = os.path.join("frontend", "static", "generated_music")

# 为 callBackUrl 提供一个默认占位符（可从配置覆盖）
DEFAULT_CALLBACK_URL = _suno_cfg.get("callback_url", "http://localhost/suno_callback_placeholder")


class SunoAPIClient:
    """
    一个简单的 Suno API 客户端
    """
    def __init__(self):
        # 检查 API 密钥是否已设置（环境变量或配置）
        if not SUNO_API_KEY:
            raise EnvironmentError("SUNO_API_KEY 未设置。请通过环境变量 SUNO_API_KEY 或 data/config.json 的 services.suno.api_key 配置。")
        
        # 定义通用的请求头部
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {SUNO_API_KEY}"
        }

    def _call_api(self, endpoint, data):
        """
        内部方法：发送 POST 请求到指定的 API 端点并处理响应。
        
        Args:
            endpoint (str): API 端点路径 (例如, "/api/v1/generate")。
            data (dict): 发送到 API 的请求体数据。
            
        Returns:
            dict: API 响应的 JSON 数据。
            
        Raises:
            Exception: 如果 API 返回的 code 不是 200 或发生请求错误。
        """
        url = f"{BASE_URL}{endpoint}"
        print(f"调用 API: {url}") # 打印正在调用的 URL
        print(f"请求数据: {json.dumps(data, indent=2, ensure_ascii=False)}") # 打印请求体

        try:
            response = requests.post(url, headers=self.headers, json=data)
            response.raise_for_status() # 检查 HTTP 错误状态 (例如, 404, 500)
            
            result = response.json()
            
            # 根据文档检查自定义的状态码
            if result.get("code") != 200:
                # 如果 API 返回非 200 的 code，抛出自定义异常
                error_msg = result.get("msg", "未知 API 错误")
                error_code = result.get("code", "N/A")
                raise Exception(f"API 错误 ({error_code}): {error_msg}")
            
            return result
            
        except requests.exceptions.RequestException as e:
            # 处理请求过程中发生的网络或 HTTP 错误
            print(f"API 请求失败: {e}")
            raise Exception(f"API 请求失败: {e}")
        except json.JSONDecodeError:
            # 处理非 JSON 响应
            print("API 返回了非 JSON 格式的响应")
            print("响应内容:", response.text)
            raise Exception("API 返回了非 JSON 格式的响应")
        except Exception as e:
            # 处理上述自定义的 API 错误
            print(f"处理 API 响应时发生错误: {e}")
            raise e

    def generate_audio(self, prompt, custom_mode=True, instrumental=True, model="V3_5", callback_url=DEFAULT_CALLBACK_URL):
        """
        调用 /api/v1/generate 端点生成音频。
        
        Args:
            prompt (str): 生成音频的文字提示。
            custom_mode (bool): 是否使用自定义模式。
            instrumental (bool): 是否生成纯音乐。
            model (str): 使用的模型 (例如, "V3_5")。
            callback_url (str, optional): 异步回调 URL。默认为 DEFAULT_CALLBACK_URL。
        
        Returns:
            dict: 包含生成任务信息的字典。
        """
        endpoint = "/api/v1/generate"
        data = {
            "prompt": prompt,
            "customMode": custom_mode,
            "instrumental": instrumental,
            "model": model,
            "callBackUrl": callback_url
        }
        # Since callback_url now has a default, we don't need to filter None values for it specifically,
        # but it's good practice if other optional params might be None.
        # data = {k: v for k, v in data.items() if v is not None} # This line is no longer strictly necessary for callBackUrl
        
        print(f"准备生成音频，提示词: '{prompt}', 回调URL: {callback_url}")
        return self._call_api(endpoint, data)

    def generate_lyrics(self, prompt, callback_url=DEFAULT_CALLBACK_URL):
        """
        调用 /api/v1/lyrics 端点生成歌词。
        
        Args:
            prompt (str): 生成歌词的文字提示。
            callback_url (str, optional): 异步回调 URL。默认为 DEFAULT_CALLBACK_URL。
            
        Returns:
            dict: 包含生成任务信息的字典。
        """
        endpoint = "/api/v1/lyrics"
        data = {
            "prompt": prompt,
            "callBackUrl": callback_url
        }
        # data = {k: v for k, v in data.items() if v is not None} # Not strictly necessary for callBackUrl now

        print(f"准备生成歌词，提示词: '{prompt}', 回调URL: {callback_url}")
        return self._call_api(endpoint, data)

    def get_task_status(self, task_id):
        """
        尝试调用 API 查询任务状态和结果。
        请注意：这个端点 '/api/v1/generate/record-info' 是一个常见猜测，
        如果您的 Suno API 服务提供商使用不同的端点，需要修改这里。

        Args:
            task_id (str): 要查询的任务 ID。

        Returns:
            dict: 包含任务状态和结果的字典。
        
        Raises:
            Exception: 如果 API 返回错误或请求失败。
        """
        # 重新尝试 SunoApi.org 文档中提到的端点
        # GET /api/v1/generate/record-info?taskId={task_id}
        endpoint = f"/api/v1/generate/record-info?taskId={task_id}"
        print(f"查询任务状态 (尝试 GET {endpoint})，任务ID: {task_id}")
        url = f"{BASE_URL}{endpoint}"
        
        try:
            response = requests.get(url, headers=self.headers) # 改回 GET 请求
            response.raise_for_status() # 检查 HTTP 错误状态
            result = response.json()

            # 打印完整的 JSON 响应以供调试
            # print(f"任务 {task_id} 的完整响应: {json.dumps(result, indent=2, ensure_ascii=False)}")

            # 检查 API 返回的 code，根据之前的经验，apibox.erweima.ai 的响应有 code 字段
            if result.get("code") != 200:
                error_msg = result.get("msg", "未知 API 错误")
                error_code = result.get("code", "N/A")
                # 对于任务未完成或排队中的情况，不应视为硬性错误并抛出异常，而是让轮询继续
                if task_id and result.get("data") and result["data"].get("status") in ["wait", "processing", "pending", "queued"]:
                    print(f"任务 {task_id} 当前状态: {result['data'].get('status')}. API msg: {error_msg}")
                    return result # 返回当前结果，让轮询逻辑判断
                raise Exception(f"API 错误 ({error_code}): {error_msg}")
            
            return result
        except requests.exceptions.RequestException as e:
            print(f"API 查询任务状态失败: {e}")
            raise Exception(f"API 查询任务状态失败: {e}")
        except json.JSONDecodeError:
            print("API 查询任务状态返回了非 JSON 格式的响应")
            print("响应内容:", response.text)
            raise Exception("API 查询任务状态返回了非 JSON 格式的响应")
        except Exception as e:
            print(f"处理 API 查询任务状态响应时发生错误: {e}")
            raise e

    def download_file(self, url, save_path):
        """
        下载文件并保存到指定路径。

        Args:
            url (str): 文件的下载链接。
            save_path (str): 本地保存文件的完整路径。
        """
        print(f"正在从 {url} 下载文件到 {save_path}")
        try:
            response = requests.get(url, stream=True)
            response.raise_for_status() # 检查 HTTP 错误
            
            # 确保保存目录存在
            save_dir_for_file = os.path.dirname(save_path)
            if not os.path.exists(save_dir_for_file):
                os.makedirs(save_dir_for_file, exist_ok=True)
                print(f"已创建目录: {save_dir_for_file}")
            
            with open(save_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            print(f"文件下载成功到: {save_path}")
        except requests.exceptions.RequestException as e:
            print(f"下载文件失败: {e}")
            raise Exception(f"下载文件失败: {e}")
        except Exception as e:
            print(f"保存文件时发生错误: {e}")
            raise Exception(f"保存文件时发生错误: {e}")

# --- 主函数示例 (修改后) ---
if __name__ == "__main__":
    print("--- Suno API 音乐生成脚本 (从JSON读取提示词) ---")
    
    # --- 新增：解析命令行参数 ---
    parser = argparse.ArgumentParser(description="Suno API 音乐生成脚本")
    parser.add_argument("--sim_name", type=str, help="指定模拟名称作为JSON文件的词干 (例如 'sim_xxxxxx')")
    args = parser.parse_args()
    # --- 结束：解析命令行参数 ---
    
    # --- 配置区域 ---
    JSON_RECORDS_DIR_TO_USE = DEFAULT_JSON_RECORDS_DIR
    
    # 根据命令行参数或默认值设置JSON文件名
    if args.sim_name:
        JSON_FILENAME_STEM_TO_USE = args.sim_name
        print(f"已从命令行参数接收到模拟名称，将使用 '{JSON_FILENAME_STEM_TO_USE}' 作为JSON文件名。")
    else:
        JSON_FILENAME_STEM_TO_USE = DEFAULT_JSON_FILENAME_STEM 
        print(f"未从命令行参数接收到模拟名称，将使用默认值 '{DEFAULT_JSON_FILENAME_STEM}' 作为JSON文件名。")

    # 音乐保存的基础目录 (相对于 generative_agents 目录)
    # 当此脚本被 AI小镇启动器.py 调用时，其 cwd (当前工作目录) 会被设置为 generative_agents 目录。
    # 因此，此处的路径应相对于 generative_agents 目录。
    # MUSIC_BASE_SAVE_DIR 的构建逻辑
    # 目标路径: <project_root>/generative_agents/frontend/static/generated_music
    # SCRIPT_DIR 是 .../generative_agents/suno-api.py, os.path.dirname(SCRIPT_DIR) 是 .../generative_agents
    # BASE_SAVE_DIR_NAME 现在是 os.path.join("frontend", "static", "generated_music")

    MUSIC_BASE_SAVE_DIR = os.path.join(RESOURCE_ROOT, BASE_SAVE_DIR_NAME)
    print(f"音乐将保存到基础目录: {MUSIC_BASE_SAVE_DIR}")

    # --- 结束配置区域 ---

    try:
        suno_client = SunoAPIClient()
        print("Suno API 客户端初始化成功。")

        json_file_path = os.path.join(JSON_RECORDS_DIR_TO_USE, f"{JSON_FILENAME_STEM_TO_USE}.json")
        
        print(f"\n尝试从以下路径加载音乐记录: {json_file_path}")

        if not os.path.exists(json_file_path):
            print(f"错误: JSON文件未找到路径 {json_file_path}")
            music_records = []
        else:
            try:
                with open(json_file_path, "r", encoding="utf-8") as f:
                    raw_list = json.load(f)
                if isinstance(raw_list, list):
                    # 仅保留包含 '音乐内容' 的记录，防串读
                    music_records = [r for r in raw_list if isinstance(r, dict) and str(r.get("音乐内容", "")).strip()]
                else:
                    music_records = []
                print(f"成功从 {JSON_FILENAME_STEM_TO_USE}.json 读取 {len(music_records)} 条有效音乐记录。")
            except json.JSONDecodeError:
                print(f"错误: JSON文件 {json_file_path} 格式错误。")
                music_records = []
            except Exception as e:
                print(f"读取JSON文件 {json_file_path} 时发生错误: {e}")
                music_records = []

        if not music_records:
            print("没有可处理的音乐记录。脚本将退出。")
        else:
            for record_idx, record in enumerate(music_records):
                music_prompt_text = record.get("音乐内容")
                agent_name = record.get("智能体")
                timestamp_from_json = record.get("时间", f"record_{record_idx}") # 获取时间或使用索引作为标识

                if not music_prompt_text or not agent_name:
                    print(f"记录 {record_idx + 1} (标识: {timestamp_from_json}) 缺少 '音乐内容' 或 '智能体'，已跳过。")
                    continue

                print(f"\n--- 处理记录 {record_idx + 1}/{len(music_records)} ---")
                print(f"  智能体: {agent_name}")
                print(f"  原始记录标识 (时间): {timestamp_from_json}")
                print(f"  音乐提示词: {music_prompt_text[:100]}...") # 打印部分提示词

                # 清理agent_name以便安全地用作路径的一部分
                cleaned_agent_name = "".join(c if c.isalnum() or c in (' ', '_', '-') else '_' for c in agent_name).rstrip()
                cleaned_agent_name = cleaned_agent_name.replace(' ', '_')
                
                # 构建特定于此任务的保存目录
                # 结构: MUSIC_BASE_SAVE_DIR / JSON_FILENAME_STEM_TO_USE / cleaned_agent_name /
                current_save_dir_for_agent = os.path.join(MUSIC_BASE_SAVE_DIR, JSON_FILENAME_STEM_TO_USE, cleaned_agent_name)
                
                # 确保目录存在
                if not os.path.exists(current_save_dir_for_agent):
                    try:
                        os.makedirs(current_save_dir_for_agent, exist_ok=True)
                        print(f"  已创建音乐保存目录: {current_save_dir_for_agent}")
                    except OSError as e:
                        print(f"  创建目录 {current_save_dir_for_agent} 失败: {e}。将尝试在下载时创建。")
                else:
                    print(f"  音乐将保存到现有目录: {current_save_dir_for_agent}")
                
                # 清理时间戳用于文件名，格式为 YYYY-MM-DD_HHMMSS
                # 假设 timestamp_from_json 格式为 "YYYY-MM-DD HH:MM:SS" 或类似
                # 例如: "2024-02-13 11:10:00" -> "2024-02-13_111000"
                try:
                    # 尝试从常见日期时间格式解析
                    from datetime import datetime
                    # 尝试几种可能的输入格式
                    possible_formats = ["%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M:%S", "%Y-%m-%d_%H%M%S"]
                    dt_object = None
                    for fmt in possible_formats:
                        try:
                            dt_object = datetime.strptime(timestamp_from_json, fmt)
                            break
                        except ValueError:
                            continue
                    
                    if dt_object:
                        cleaned_timestamp_for_filename = dt_object.strftime("%Y-%m-%d_%H%M%S")
                    else:
                        # 如果所有格式都解析失败，使用原始清理方法作为回退
                        print(f"警告: 时间戳 '{timestamp_from_json}' 无法通过标准格式解析。将使用默认清理方式。")
                        cleaned_timestamp_for_filename = timestamp_from_json.replace(':', '').replace(' ', '_').replace('-', '')
                except Exception as e_time_format:
                    print(f"处理时间戳 '{timestamp_from_json}' 时发生意外错误: {e_time_format}。将使用默认清理方式。")
                    cleaned_timestamp_for_filename = timestamp_from_json.replace(':', '').replace(' ', '_').replace('-', '')

                # 默认生成音乐模型
                audio_generation_params = {
                    "prompt": music_prompt_text,
                    "custom_mode": True,
                    "instrumental": True, 
                    "model": "V4_5PLUS", # 可以根据需要修改模型
                    "callback_url": DEFAULT_CALLBACK_URL # 总是传递回调URL
                }
                
                print(f"\n尝试为智能体 '{agent_name}' 生成音频...")
                try:
                    audio_response = suno_client.generate_audio(**audio_generation_params)
                    # print("生成音频 API 调用成功！") # 在 _call_api 中已有更详细的日志
                    # print("响应数据:", json.dumps(audio_response, indent=2, ensure_ascii=False))
                    
                    task_id = None
                    if audio_response and audio_response.get('code') == 200 and audio_response.get('data'):
                         task_id = audio_response['data'].get('taskId')

                    if task_id:
                        print(f"获取到任务 ID: {task_id}")
                        print("等待生成完成，开始轮询...")
                        
                        max_retries = 60 
                        retry_delay = 10 # 增加轮询间隔，避免过于频繁
                        audio_url = None
                        
                        for i in range(max_retries):
                            try:
                                time.sleep(retry_delay)
                                status_response = suno_client.get_task_status(task_id)
                                
                                task_data_from_response = status_response.get('data', {})
                                task_status = task_data_from_response.get('status', '').lower()
                                
                                print(f"轮询 {i+1}/{max_retries}: 任务 {task_id} 状态 - {task_status.upper() if task_status else '未知'}")
                                
                                if task_status == 'success':
                                     suno_data_list = status_response.get('data', {}).get('response', {}).get('sunoData', [])
                                     if suno_data_list and isinstance(suno_data_list, list) and len(suno_data_list) > 0:
                                         # 假设我们总是取第一个结果的音频
                                         if suno_data_list[0] and isinstance(suno_data_list[0], dict):
                                             audio_url = suno_data_list[0].get('audioUrl')
                                         else:
                                             print(f"sunoData[0] 格式不正确: {suno_data_list[0]}")
                                     elif not suno_data_list:
                                         print("任务状态为 success，但 sunoData 列表为空。可能需要检查API响应结构。")

                                     if audio_url:
                                         print(f"任务完成，获取到音频链接: {audio_url}")
                                         break 
                                     else:
                                         print("任务完成，但未能从预期的路径中找到音频链接。")
                                         print("status_response['data']['response'] 内容:", status_response.get('data', {}).get('response', {}))
                                         break 
                                elif task_status == 'failed' or task_status == 'error':
                                     error_message_from_api = task_data_from_response.get('response', {}).get('message') or task_data_from_response.get('message', '无详细错误信息')
                                     print(f"任务失败或出错: {error_message_from_api}")
                                     break 
                                elif task_status in ['wait', 'processing', 'pending', 'queued']:
                                    # 这些是中间状态，继续轮询
                                    pass
                                else:
                                    # 未知或非预期的完成状态
                                    print(f"任务返回未知或非预期状态: {task_status}。响应: {status_response}")
                                    # 可以选择在此处中断或继续轮询，取决于API行为
                                    # break # 如果不确定如何处理，可以中断

                            except Exception as e_poll:
                                print(f"轮询任务状态时发生错误: {e_poll}")
                                if i == max_retries - 1:
                                    print("达到最大轮询次数，停止轮询。")
                                    # raise # 生产环境中可以考虑重新抛出，调试时可以注释掉以继续处理其他记录
                                break # 发生轮询错误时，中断当前记录的轮询

                        if audio_url:
                            file_name = f"{cleaned_timestamp_for_filename}_{task_id[:8]}.mp3" 
                            save_path_full = os.path.join(current_save_dir_for_agent, file_name)
                            
                            try:
                                 suno_client.download_file(audio_url, save_path_full)
                                 # 构建相对路径用于显示 (相对于项目根目录)
                                 relative_save_path = os.path.relpath(save_path_full, os.path.dirname(SCRIPT_DIR))
                                 print(f"生成的音乐已保存到相对路径: {relative_save_path}")
                            except Exception as e_download:
                                 print(f"保存音乐文件 '{save_path_full}' 失败: {e_download}")
                        else:
                             print(f"未能获取音频下载链接，无法为记录 {record_idx + 1} ({agent_name}) 保存音乐。")
                    else:
                        print(f"未能从API响应中获取任务ID，无法轮询状态。记录 {record_idx + 1} ({agent_name})")

                except Exception as e_generate:
                    print(f"为记录 {record_idx + 1} ({agent_name}) 生成音频失败: {e_generate}")
                
                print(f"--- 完成处理记录 {record_idx + 1} ({agent_name}) ---")
            
            print("\n所有音乐记录处理完毕。")

    except EnvironmentError as e:
        print(f"客户端初始化失败: {e}")
    except Exception as e:
        print(f"执行过程中发生意外错误: {e}")
        import traceback
        traceback.print_exc()

    print("\n--- 脚本执行完毕 ---")
