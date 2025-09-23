from openai import OpenAI
import os
import sys
import json # Added for parsing tool arguments
import traceback # Added for more detailed error info if needed
from datetime import datetime # 新增导入 datetime
import argparse # 新增导入 argparse

# 统一控制台编码为 UTF-8，避免冻结模式中文乱码
try:
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    os.environ.setdefault("PYTHONUTF8", "1")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# --- 新增：命令行参数解析 ---
parser = argparse.ArgumentParser(description="Gemini API Cellular Automata HTML/JS Generator")
parser.add_argument(
    "--sim_name",
    type=str,
    default=None, 
    help="The simulation name (stem of the JSON file in quantum-computing-records, e.g., sim_20250605_103304)"
)
args = parser.parse_args()
# --- 结束：命令行参数解析 ---

# --- 新增：获取脚本/可执行所在目录 ---
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


SCRIPT_DIR = _get_base_dir()
RESOURCE_ROOT = _get_resource_root(SCRIPT_DIR)

# 统一解析 results 目录（兼容开发与打包，并支持外部注入 GA_RESULTS_DIR）
def _resolve_records_dir(subdir: str) -> str:
    """返回首个存在的 results 子目录；如都不存在，返回首选并尽量创建。
    优先顺序：
    0) $GA_RESULTS_DIR/<subdir> （启动器注入，最高优先）
    1) SCRIPT_DIR/results/<subdir>
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
        os.path.join(SCRIPT_DIR, "results", subdir),
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

# --- 新增：从配置与环境变量读取 Gemini 设置 ---
CONFIG_PATH = os.path.join(RESOURCE_ROOT, "data", "config.json")
CONFIG_GEMINI_PATH = os.path.join(RESOURCE_ROOT, "data", "config-gemini.json")
config_data = {}
config_gemini_data = {}
try:
    with open(CONFIG_PATH, "r", encoding="utf-8") as cfg_file:
        config_data = json.load(cfg_file)
except FileNotFoundError:
    print(f"警告: 配置文件未找到: {CONFIG_PATH}，将尝试备用配置并使用环境变量或默认值。")
except Exception as e_cfg:
    print(f"警告: 读取配置文件失败: {e_cfg}，将尝试备用配置并使用环境变量或默认值。")

try:
    with open(CONFIG_GEMINI_PATH, "r", encoding="utf-8") as cfg_g_file:
        config_gemini_data = json.load(cfg_g_file)
except FileNotFoundError:
    # 允许没有备用文件
    config_gemini_data = {}
except Exception as e_cfg2:
    print(f"警告: 读取备用配置文件失败: {e_cfg2}。")

gemini_cfg = (config_data.get("services", {}).get("gemini", {}) if isinstance(config_data, dict) else {})
fallback_llm_cfg = (config_gemini_data.get("agent_base", {}).get("think", {}).get("llm", {}) if isinstance(config_gemini_data, dict) else {})
fallback_api_key = (config_gemini_data.get("api_keys", {}) or {}).get("GEMINI_API_KEY", "")

API_KEY = (
    os.getenv("GEMINI_API_KEY")
    or os.getenv("GOOGLE_API_KEY")
    or os.getenv("OPENAI_API_KEY")
    or gemini_cfg.get("api_key", "")
    or fallback_api_key
)
BASE_URL = (
    os.getenv("GEMINI_BASE_URL")
    or gemini_cfg.get("base_url")
    or fallback_llm_cfg.get("base_url")
    or "https://generativelanguage.googleapis.com/v1beta/openai/"
)
model_name = (
    os.getenv("GEMINI_MODEL")
    or gemini_cfg.get("model")
    or fallback_llm_cfg.get("model")
    or "gemini-2.5-flash"
)

if not API_KEY:
    print("错误：缺少 GEMINI_API_KEY/GOOGLE_API_KEY 或配置中的 Gemini API Key。请在环境变量或 data/config.json 的 services.gemini.api_key，或 data/config-gemini.json 的 api_keys.GEMINI_API_KEY 中设置。")
    sys.exit(1)

client = OpenAI(
    api_key=API_KEY,
    base_url=BASE_URL # 注意这里的 openai 后缀
)

# Dynamically read the context code from the file
# --- 修改：使用 RESOURCE_ROOT 构建 context_file_path ---
# 尝试多路径寻找上下文文件，兼容打包后相对路径差异
_context_candidates = [
    os.path.join(SCRIPT_DIR, "conway_game_of_life copy.py"),
    os.path.join(RESOURCE_ROOT, "..", "conway_game_of_life copy.py"),
    os.path.join(os.path.dirname(RESOURCE_ROOT), "conway_game_of_life copy.py"),
]
context_file_path = None
for _p in _context_candidates:
    if os.path.isfile(_p):
        context_file_path = _p
        break
if context_file_path is None:
    # 维持原有错误日志行为
    context_file_path = os.path.join(RESOURCE_ROOT, "..", "conway_game_of_life copy.py")
# --- 结束修改 ---
context_code_from_file = ""
try:
    with open(context_file_path, "r", encoding="utf-8") as f:
        context_code_from_file = f.read()
    print(f"已成功读取上下文文件: {context_file_path}")
except FileNotFoundError:
    print(f"错误: 上下文文件 {context_file_path} 未找到。请确保该文件存在于脚本同目录下，或提供正确路径。")
    # 你可以选择在这里退出脚本，或者使用一个空的/默认的上下文
    # exit()
except Exception as e_read:
    print(f"读取上下文文件 {context_file_path} 时发生错误: {e_read}")
    # exit()

# --- 新增：读取量子计算内容作为核心规则提示 ---
# quantum_prompt_from_json = "" # 将在循环内赋值
# quantum_sim_name = "sim_default" # 将在读取JSON后，循环外赋值
# quantum_agent_name = "agent_default" # 将在循环内赋值
all_quantum_records = [] # 用于存储所有记录
input_json_filename_stem = "sim_default" # 用于存储JSON文件名（不含后缀）

# --- 修改：使用 SCRIPT_DIR 构建 quantum_json_path --- 
# quantum_json_path = os.path.join(SCRIPT_DIR, "results", "quantum-computing-records", "sim_20250605_132132.json")
# --- 结束修改 ---

quantum_records_base_dir = _resolve_records_dir("quantum-computing-records")

if args.sim_name:
    quantum_json_filename = f"{args.sim_name}.json"
    quantum_json_path = os.path.join(quantum_records_base_dir, quantum_json_filename)
    print(f"将使用命令行参数指定的量子记录文件: {quantum_json_path}")
else:
    default_sim_name_for_direct_run = "sim_20250605_103304" # 默认文件，如果脚本直接运行且未提供参数
    quantum_json_filename = f"{default_sim_name_for_direct_run}.json"
    quantum_json_path = os.path.join(quantum_records_base_dir, quantum_json_filename)
    print(f"警告: 未通过 --sim_name 参数提供模拟名称。")
    print(f"将尝试使用默认的量子记录文件: {quantum_json_path}")

try:
    with open(quantum_json_path, "r", encoding="utf-8") as f_quantum:
        raw_list = json.load(f_quantum)
        if isinstance(raw_list, list):
            # 仅保留包含 '量子计算内容' 的记录，防串读
            all_quantum_records = [r for r in raw_list if isinstance(r, dict) and str(r.get("量子计算内容", "")).strip()]
        else:
            all_quantum_records = []
        input_json_filename_stem = os.path.splitext(os.path.basename(quantum_json_path))[0]
        print(f"已成功从 {quantum_json_path} 读取 {len(all_quantum_records)} 条有效量子计算记录。")
except FileNotFoundError:
    print(f"错误: 量子计算记录文件 {quantum_json_path} 未找到。")
    all_quantum_records = [] # 确保为空列表
except json.JSONDecodeError:
    print(f"错误: 解析量子计算记录文件 {quantum_json_path} JSON失败。")
    all_quantum_records = [] # 确保为空列表
except Exception as e_quantum_read:
    print(f"读取量子计算记录文件 {quantum_json_path} 时发生未知错误: {e_quantum_read}")
    all_quantum_records = [] # 确保为空列表
# --- 结束：读取量子计算内容 ---


# Prompt for the AI, now using the dynamically loaded context_code_from_file
# --- 修改：将量子计算内容整合到主提示词中 ---
# prompt_message 将在循环内构建

# Tool definition (remains the same, describes how AI can ask for code execution)
tools = [
    {
        "type": "function",
        "function": {
            "name": "execute_python_code",
            "description": "Executes a given Python code snippet and returns its output. Used for generating and running simulations, calculations, etc.",
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "The raw Python code to be executed."
                    }
                },
                "required": ["code"]
            }
        }
    }
]

# --- 新增：动态构建输出路径和文件名 --- 
# 基础输出目录
# --- 修改：使用 RESOURCE_ROOT 构建基础代码输出目录 (移到循环外) ---
BASE_HTML_OUTPUT_DIR = os.path.join(RESOURCE_ROOT, "frontend", "static", "generated_html_sims")
# --- 结束修改 ---

# --- 修改：将API调用和文件保存逻辑放入循环中，为每个记录执行一次 ---
if not all_quantum_records:
    print("没有从JSON文件加载到任何量子计算记录，脚本将退出。")
else:
    print(f"\n开始依次处理 {len(all_quantum_records)} 条量子计算记录...")
    for record_index, current_record in enumerate(all_quantum_records):
        print(f"\n--- 正在处理记录 {record_index + 1} / {len(all_quantum_records)} ---")

        current_quantum_prompt = current_record.get("量子计算内容", "")
        current_agent_name = current_record.get("智能体", "unknown_agent")
        record_time_str = current_record.get("时间", datetime.now().strftime("%Y-%m-%d %H_%M_%S")) # 获取记录中的时间，若无则用当前时间

        if not current_quantum_prompt:
            print("  当前记录缺少 '量子计算内容'，已跳过。")
            continue
        
        print(f"  智能体: {current_agent_name}")
        print(f"  记录时间: {record_time_str}")
        print(f"  量子计算内容 (前50字符): {current_quantum_prompt[:50]}...")

        # 构建新的 prompt_message，要求输出HTML/JS/Canvas
        prompt_message = f"""You are an expert web developer specializing in creating interactive simulations with HTML, JavaScript, and the HTML5 Canvas API.
Your task is to invent a **brand new and completely original set of rules** for a 2D cellular automaton based on the specific concept provided below. Then, you must implement this automaton as a **single, self-contained HTML file**.

**INSPIRATION FOR THE NEW RULES (USE THIS SPECIFIC CONCEPT):**
Your primary task is to design the new cellular automaton rules based on the following concept description. Expand upon it, refine it, and make it work as a visual simulation. If the description is abstract or incomplete, use your creativity to fill in the gaps and make it concrete and simulatable:
```text
{current_quantum_prompt}
```

Your new automaton must be **distinctly different** from common examples like Conway's Game of Life.
It must define at least 3 or 4 distinct cell states (e.g., 'EMPTY', 'STATE_A', 'STATE_B', 'STATE_C') directly inspired by or compatible with the rules described in the concept above. Clearly define the rules for how these states transition based on their neighbors.

**OUTPUT REQUIREMENTS:**
Generate a complete, runnable, **single HTML file** that:
1.  Includes all necessary HTML structure (<!DOCTYPE html>, <html>, <head>, <body>).
2.  Contains a `<canvas id="simulationCanvas"></canvas>` element where the simulation will be rendered.
3.  Includes all JavaScript code within `<script>` tags. This JavaScript should:
    a.  Implement the logic for your newly invented cellular automaton rules.
    b.  Initialize a reasonably sized grid (e.g., 60 rows by 100 columns) with an interesting starting pattern relevant to your new rules.
    c.  Simulate the automaton for a number of generations or run indefinitely.
    d.  Render the grid state on the HTML5 Canvas. Each cell state in your new automaton should be represented by a distinct color (e.g., "#RRGGBB" hex codes). Clearly define these colors in your JavaScript.
    e.  (Optional, but highly recommended for usability) Include basic HTML buttons (e.g., `<button id="startPauseBtn">Start/Pause</button>`, `<button id="resetBtn">Reset</button>`) and corresponding JavaScript functions for controls.
4.  The HTML file should be self-contained. Avoid external CSS or JavaScript files if possible; inline CSS within `<style>` tags is acceptable if needed for basic layout of canvas and buttons.
5.  The simulation should ideally start automatically on page load, or after a "Start" button is pressed if you include controls.

**CRITICAL INSTRUCTION**: Your entire response should be **ONLY the raw HTML code for this single file, and nothing else**. Do not include any surrounding text, no explanations, no markdown code fences (like ```html ... ```), just the pure, unadulterated HTML code itself, starting from <!DOCTYPE html>.
"""

        # --- 动态构建输出路径和文件名 (基于当前记录) ---
        # 基础输出目录 (使用 SCRIPT_DIR)
        # BASE_CODE_OUTPUT_DIR = os.path.join(SCRIPT_DIR, "frontend", "static", "generated_code") # 已移到循环外

        # 清理智能体名称以安全用于路径
        cleaned_agent_name_for_path = "".join(c if c.isalnum() or c in (' ', '_', '-') else '_' for c in current_agent_name).rstrip().replace(' ', '_')
        if not cleaned_agent_name_for_path:
            cleaned_agent_name_for_path = "unknown_agent"

        # 新的文件名格式化逻辑 (确保格式为 YYYY-MM-DD_HHMMSS)
        try:
            # 假设 record_time_str 格式为 "YYYY-MM-DD HH_MM_SS" (来自 strftime 的默认情况)
            # 或 "YYYY-MM-DD HH:MM:SS" (例如，从 JSON 文件中读取的)
            date_part, time_part_original = record_time_str.split(" ", 1)
            # date_part 示例: "2024-02-13"
            # time_part_original 示例: "11_10_00" 或 "11:10:00"
            time_part_cleaned_for_filename = time_part_original.replace(":", "").replace("_", "") # 转换为 "111000"
            filename_stem_for_html = f"{date_part}_{time_part_cleaned_for_filename}" # 格式: YYYY-MM-DD_HHMMSS
        except ValueError:
            # 如果 record_time_str 的格式不符合预期 (例如，日期和时间部分之间没有空格)
            print(f"  警告: 记录时间 \"{record_time_str}\" 的格式无法按预期解析。")
            # 使用当前系统时间并按指定格式生成文件名作为后备方案
            current_time_for_filename = datetime.now()
            date_part_fallback = current_time_for_filename.strftime("%Y-%m-%d")
            time_part_fallback = current_time_for_filename.strftime("%H%M%S")
            filename_stem_for_html = f"{date_part_fallback}_{time_part_fallback}" # 格式: YYYY-MM-DD_HHMMSS
            print(f"  将使用当前系统时间生成文件名: {filename_stem_for_html}.html")
        
        output_html_filename = f"{filename_stem_for_html}.html" # 例如: 2024-02-13_111000.html

        # 构建完整的保存目录和文件路径
        # 使用从JSON文件名提取的 input_json_filename_stem 作为模拟名称
        target_save_dir = os.path.join(BASE_HTML_OUTPUT_DIR, input_json_filename_stem, cleaned_agent_name_for_path)
        output_filepath = os.path.join(target_save_dir, output_html_filename)
        # --- 结束：动态构建输出路径和文件名 ---

        try:
            print(f"  向 Gemini ({model_name}) 发送请求以生成HTML模拟 (记录 {record_index + 1})...")

            messages = [
                {"role": "system", "content": "You are a web developer creating HTML/JS/Canvas simulations. Output only raw HTML code as instructed."},
                {"role": "user", "content": prompt_message}
            ]

            response = client.chat.completions.create(
                model=model_name,
                messages=messages,
                # No tools are defined or chosen, expecting direct content response
                # tool_choice="auto", # Removed
                extra_body={"reasoning_effort": "low"} # Retained, might help with complex generation
            )

            message = response.choices[0].message

            if message.content:
                html_code_to_save = message.content
                # Basic check if it looks like HTML
                if html_code_to_save.strip().lower().startswith("<!doctype html>") or \
                   html_code_to_save.strip().lower().startswith("<html>"):
                    try:
                        os.makedirs(target_save_dir, exist_ok=True)
                        print(f"    将HTML代码保存到: {output_filepath}")
                        with open(output_filepath, "w", encoding="utf-8") as f:
                            f.write(html_code_to_save)
                        print(f"  成功! 记录 {record_index + 1} 的HTML模拟已保存。")
                    except OSError as e_mkdir:
                        print(f"    创建目录 {target_save_dir} 失败: {e_mkdir}。HTML未保存。")
                    except Exception as e_save_file:
                        print(f"    保存文件到 {output_filepath} 时发生错误: {e_save_file}")
                else:
                    print(f"    错误：AI返回的内容不像HTML (记录 {record_index + 1})。内容预览 (前100字符):")
                    print(html_code_to_save[:100])
                    print(f"    完整内容已记录到控制台日志。") # User can check full log if needed
            # Check for tool_calls defensively, though not expected
            elif message.tool_calls:
                print(f"    错误：AI意外地请求了工具 (记录 {record_index + 1})，而非直接返回HTML。工具调用: {message.tool_calls}")
            else:
                print(f"  AI没有返回预期的HTML内容，也没有工具调用 (记录 {record_index + 1})。响应不符合预期。")
                print(f"  完整响应消息: {message}")

        except Exception as e_api_call:
            print(f"\n  处理记录 {record_index + 1} 时调用API或处理响应时发生严重错误：{e_api_call}")
            print("  请检查以下几点：")
            print("  1. 你的 API 密钥是否正确填写在脚本中？")
            print(f"  2. 模型名称 '{model_name}' 是否正确且你的 API 密钥有权访问？")
            print("  3. 你的网络连接是否畅通且可以访问 Google API 服务？")
            print("  4. OpenAI库是否已正确安装？")
            print("\n  详细错误信息:")
            traceback.print_exc()
        
        print(f"--- 完成处理记录 {record_index + 1} ---")
    
    print("\n所有量子计算记录处理完毕。")

# except Exception as e: # 最外层的 try-except 已被循环内的 try-except 替代，或可以保留作为最终捕获
#     print(f"\n脚本执行过程中发生意外的顶层错误：{e}")
#     print("\n详细错误信息:")
#     traceback.print_exc() 