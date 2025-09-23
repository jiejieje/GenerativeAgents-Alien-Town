"""
这个模块用于压缩和处理模拟结果:
1. 将多个存档文件合并成一个动作记录文件(用于回放)
2. 生成Markdown格式的模拟报告
"""

import os  # 导入操作系统模块,用于文件和目录操作
import sys  # 兼容 PyInstaller 冻结运行时路径
import json  # 导入json模块,用于处理JSON数据
import argparse  # 导入命令行参数解析模块
from datetime import datetime  # 导入日期时间处理模块

from modules.maze import Maze  # 导入迷宫类,用于计算路径

# 输出文件名称
file_markdown = "simulation.md"  # Markdown报告文件名
file_movement = "movement.json"  # 动作记录文件名

frames_per_step = 60  # 每个step包含的帧数(用于动画平滑显示)

# 强制 UTF-8 日志与 I/O，避免中文在 Windows/管道中出现乱码
try:
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    os.environ.setdefault("PYTHONUTF8", "1")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def _results_root() -> str:
    """确定结果根目录，优先使用 GA_RESULTS_DIR，其次使用运行目录下的 results。"""
    try:
        env_root = (os.environ.get("GA_RESULTS_DIR") or "").strip()
        base_dir = os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else os.getcwd()
        candidates = [
            env_root,
            os.path.join(base_dir, "results"),
            os.path.join(os.getcwd(), "results"),
        ]
        for c in candidates:
            if c and os.path.isdir(c):
                return c
        # 若都不存在，返回优先候选，外侧代码会按需创建
        return env_root or os.path.join(base_dir, "results")
    except Exception:
        return os.path.join(os.getcwd(), "results")


def get_stride(json_files):
    """从存档文件中读取时间步长
    json_files: 存档文件列表
    返回: 时间步长(分钟)
    """
    if len(json_files) < 1:  # 如果没有存档文件
        return 1  # 返回默认步长1

    # 读取最后一个存档文件中的步长设置
    with open(json_files[-1], "r", encoding="utf-8") as f:
        config = json.load(f)

    return config["stride"]  # 返回配置的步长值


def get_location(address):
    """将地址列表转换为可读的位置字符串
    address: 地址列表
    返回: 位置描述字符串
    """
    # 不需要显示address第一级("the Ville")
    location = "，".join(address[1:])  # 用中文逗号连接地址各级

    return location


def _resource_root():
    base_dir = os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else os.getcwd()
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


def _safe_read_agent_json(agent_name):
    """尝试读取代理人的 agent.json，找不到时返回 None。"""
    json_path = os.path.join(_resource_root(), "frontend", "static", "assets", "village", "agents", agent_name, "agent.json")
    if os.path.exists(json_path):
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"Failed to read {json_path}: {e}")
            return None
    else:
        print(f"agent.json not found for '{agent_name}' at {json_path}, will fallback to checkpoint data if available.")
        return None


def insert_frame0(init_pos, movement, agent_name, agent_data=None):
    """插入第0帧数据(Agent的初始状态)
    init_pos: 初始位置字典
    movement: 动作记录字典
    agent_name: 代理人名称
    agent_data: 当 agent.json 缺失时，使用存档中的该代理数据进行回退
    """
    key = "0"  # 第0帧的键
    if key not in movement.keys():  # 如果第0帧数据不存在
        movement[key] = dict()  # 创建空字典

    json_data = _safe_read_agent_json(agent_name)

    # 填充地址与坐标（优先 agent.json，其次使用存档中的 agent_data 回退）
    address = None
    coord = None

    if json_data is not None:
        try:
            # 兼容新版数据结构：spatial.tree.the Ville
            tree = (json_data.get("spatial") or {}).get("tree") or json_data.get("tree") or {}
            ville = tree.get("the Ville", {})
            first_ville_area = next(iter(ville.keys()))
            first_sub_area = next(iter(ville[first_ville_area].keys()))
            address = ["the Ville", first_ville_area, first_sub_area]
        except Exception as e:
            print(f"Error accessing living_area for {agent_name} from tree: {e}")
            address = ["the Ville", "Unknown Area", "Unknown SubArea"]
        coord = json_data.get("coord")
    
    # 使用存档数据回退
    if (address is None or coord is None) and agent_data is not None:
        try:
            addr_from_checkpoint = agent_data["action"]["event"]["address"]
            # 规范为去除 the Ville 第一级（get_location 内会处理），这里保持原样
            address = addr_from_checkpoint
        except Exception:
            address = ["the Ville", "Unknown Area", "Unknown SubArea"]
        coord = agent_data.get("coord", [0, 0])

    # 仍为空则提供最终兜底
    if address is None:
        address = ["the Ville", "Unknown Area", "Unknown SubArea"]
    if coord is None:
        coord = [0, 0]

    location = get_location(address if isinstance(address, list) else ["the Ville"] + list(address))

    # 保存初始位置
    init_pos[agent_name] = coord
    # 设置第0帧的状态数据
    movement[key][agent_name] = {
        "location": location,
        "movement": coord,
        "description": "正在睡觉",
    }

    # 保存代理人的初始状态信息
    if json_data is not None:
        movement["description"][agent_name] = {
            "currently": json_data.get("currently", ""),
            "scratch": json_data.get("scratch", {}),
        }
    elif agent_data is not None:
        movement["description"][agent_name] = {
            "currently": agent_data.get("currently", ""),
            "scratch": agent_data.get("scratch", {}),
        }


def generate_movement(checkpoints_folder, compressed_folder, compressed_file):
    """从所有存档文件中提取数据(用于回放)
    checkpoints_folder: 存档文件夹路径
    compressed_folder: 压缩文件输出文件夹路径
    compressed_file: 压缩文件名
    返回: 包含所有动作记录的字典
    """
    # 构建输出文件路径
    movement_file = os.path.join(compressed_folder, compressed_file)

    # 读取对话记录文件
    conversation_file = "conversation.json"
    conversation = {}
    if os.path.exists(os.path.join(checkpoints_folder, conversation_file)):
        with open(os.path.join(checkpoints_folder, conversation_file), "r", encoding="utf-8") as f:
            conversation = json.load(f)

    # 获取所有存档文件列表(按名称排序)
    files = sorted(os.listdir(checkpoints_folder))
    json_files = list()
    for file_name in files:
        if file_name.endswith(".json") and file_name != conversation_file:
            json_files.append(os.path.join(checkpoints_folder, file_name))

    # 初始化数据结构
    persona_init_pos = dict()  # 存储所有代理人的初始位置
    all_movement = dict()  # 存储所有动作记录
    all_movement["description"] = dict()  # 存储描述信息
    all_movement["conversation"] = dict()  # 存储对话记录
    all_movement["0"] = all_movement.get("0", {})  # 确保存在第0帧容器

    # 获取时间步长设置
    stride = get_stride(json_files)
    sec_per_step = stride  # 每步对应的秒数

    # 构建结果数据结构
    result = {
        "start_datetime": "",  # 起始时间
        "stride": stride,  # 每个step对应的分钟数(必须与生成时的参数一致)
        "sec_per_step": sec_per_step,  # 回放时每一帧对应的秒数
        "persona_init_pos": persona_init_pos,  # 每个Agent的初始位置
        "all_movement": all_movement,  # 所有Agent在每个step中的位置变化
    }

    # 记录上一次的位置信息
    last_location = dict()

    # 加载地图数据,用于计算Agent移动路径
    json_path = os.path.join(_resource_root(), "frontend", "static", "assets", "village", "maze.json")
    with open(json_path, "r", encoding="utf-8") as f:
        json_data = json.load(f)
        maze = Maze(json_data, None)  # 创建迷宫实例

    # 遍历所有存档文件
    for file_name in json_files:
        # 读取存档文件内容
        with open(file_name, "r", encoding="utf-8") as f:
            json_data = json.load(f)
            step = json_data["step"]  # 获取当前步数
            agents = json_data["agents"]  # 获取所有代理人数据

            # 如果是第一个存档,保存起始时间
            if len(result["start_datetime"]) < 1:
                t = datetime.strptime(json_data["time"], "%Y%m%d-%H:%M")  # 解析时间字符串
                result["start_datetime"] = t.isoformat()  # 转换为ISO格式

            # 遍历当前存档中的所有代理人
            for agent_name, agent_data in agents.items():
                # 如果是第一步,需要插入第0帧数据
                if step == 1:
                    # 允许使用存档数据作为回退，避免 agent.json 缺失导致崩溃
                    insert_frame0(persona_init_pos, all_movement, agent_name, agent_data)

                # 获取起点和终点坐标
                # 源坐标：上一次位置 > 第0帧 > 存档中的当前坐标
                default_initial = {"movement": agent_data.get("coord", [0, 0]), "location": get_location(agent_data["action"]["event"].get("address", ["the Ville"]))}
                source_coord = last_location.get(
                    agent_name,
                    all_movement["0"].get(agent_name, default_initial)
                )["movement"]
                target_coord = agent_data["coord"]  # 目标位置
                
                # 获取目标位置的地址描述
                location = get_location(agent_data["action"]["event"]["address"])
                if location is None:  # 如果没有有效地址
                    # 使用上一次的位置描述,如果没有则使用初始位置描述
                    location = last_location.get(
                        agent_name,
                        all_movement["0"].get(agent_name, default_initial)
                    )["location"]
                    path = [source_coord]  # 路径只包含当前位置
                else:
                    # 计算从起点到终点的路径
                    path = maze.find_path(source_coord, target_coord)

                # 初始化对话相关变量
                had_conversation = False  # 是否有对话
                step_conversation = ""  # 对话内容
                persons_in_conversation = []  # 参与对话的人员

                # 处理当前时间点的对话记录
                step_time = json_data["time"]  # 获取当前时间点
                if step_time in conversation.keys():  # 如果当前时间点有对话记录
                    for chats in conversation[step_time]:  # 遍历所有对话
                        for persons, chat in chats.items():  # 遍历每组对话的参与者和内容
                            # 提取对话参与者(分割格式: "人物A -> 人物B @ 位置")
                            persons_in_conversation.append(persons.split(" @ ")[0].split(" -> "))
                            # 添加对话地点信息
                            step_conversation += f"\n地点：{persons.split(' @ ')[1]}\n\n"
                            # 添加对话内容
                            for c in chat:
                                agent = c[0]  # 说话的代理人
                                text = c[1]  # 说话内容
                                step_conversation += f"{agent}：{text}\n"

                # 处理每一帧的动作(将每个step细分为多帧以实现平滑动画)
                for i in range(frames_per_step):
                    moving = len(path) > 1  # 判断是否在移动(路径点数大于1)
                    if len(path) > 0:  # 如果还有路径点
                        movement = list(path[0])  # 获取当前路径点
                        path = path[1:]  # 移除已使用的路径点
                        # 更新位置记录
                        if agent_name not in last_location.keys():
                            last_location[agent_name] = dict()
                        last_location[agent_name]["movement"] = movement
                        last_location[agent_name]["location"] = location
                    else:
                        movement = None  # 没有路径点时设为None

                    if moving:  # 如果正在移动
                        action = f"前往 {location}"  # 显示移动目标
                    elif movement is not None:  # 如果有位置但不在移动
                        # 获取动作描述
                        action = agent_data["action"]["event"]["describe"]
                        if len(action) < 1:  # 如果没有描述
                            # 使用谓语+对象作为描述
                            action = f'{agent_data["action"]["event"]["predicate"]}{agent_data["action"]["event"]["object"]}'

                        # 检查该代理人是否参与了对话
                        for persons in persons_in_conversation:
                            if agent_name in persons:  # 如果代理人在对话参与者列表中
                                had_conversation = True  # 标记为有对话
                                break

                        # 为特定动作添加表情图标
                        if "睡觉" in action:  # 如果是睡觉动作
                            action = "😴 " + action  # 添加睡觉表情
                        elif had_conversation:  # 如果有对话
                            action = "💬 " + action  # 添加对话表情

                    # 生成当前帧的键名(基于step和帧序号)
                    step_key = "%d" % ((step-1) * frames_per_step + 1 + i)
                    if step_key not in all_movement.keys():  # 如果该帧不存在
                        all_movement[step_key] = dict()  # 创建新的帧数据字典

                    # 如果有移动数据,记录这一帧的状态
                    if movement is not None:
                        all_movement[step_key][agent_name] = {
                            "location": location,  # 位置描述
                            "movement": movement,  # 坐标
                            "action": action,  # 动作描述
                        }
                # 保存当前时间点的对话记录
                all_movement["conversation"][step_time] = step_conversation

    # 将所有数据写入文件
    with open(movement_file, "w", encoding="utf-8") as f:
        f.write(json.dumps(result, indent=2, ensure_ascii=False))

    return result  # 返回处理后的数据


def generate_report(checkpoints_folder, compressed_folder, compressed_file):
    """生成Markdown格式的模拟报告
    checkpoints_folder: 存档文件夹路径
    compressed_folder: 压缩文件输出文件夹路径
    compressed_file: 输出文件名
    """
    # 用于记录代理人的上一个状态
    last_state = dict()

    # 读取对话记录文件
    conversation_file = "conversation.json"
    conversation = {}
    if os.path.exists(os.path.join(checkpoints_folder, conversation_file)):
        with open(os.path.join(checkpoints_folder, conversation_file), "r", encoding="utf-8") as f:
            conversation = json.load(f)

    def extract_description():
        """提取并格式化所有代理人的基本信息
        返回: Markdown格式的基础人设描述
        """
        markdown_content = "# 基础人设\n\n"  # 标题
        # 避免导入 start.py，直接扫描资源目录以获得 personas 列表
        agents_dir = os.path.join(_resource_root(), "frontend", "static", "assets", "village", "agents")
        try:
            persona_names = sorted([d for d in os.listdir(agents_dir) if os.path.isdir(os.path.join(agents_dir, d))])
        except Exception:
            persona_names = []
        for agent_name in persona_names:  # 遍历所有代理人
            # 清理名称中可能出现的问题
            clean_name = agent_name.replace(" ", "")
            # 读取代理人的配置文件
            json_path = os.path.join(_resource_root(), "frontend", "static", "assets", "village", "agents", agent_name, "agent.json")
            try:
                with open(json_path, "r", encoding="utf-8") as f:
                    json_data = json.load(f)
                # 添加代理人名称作为二级标题
                markdown_content += f"## {clean_name}\n\n"
                # 添加代理人的基本信息
                markdown_content += f"年龄：{json_data.get('scratch', {}).get('age', '未知')}岁  \n"
                markdown_content += f"先天：{json_data.get('scratch', {}).get('innate', '未知')}  \n"
                markdown_content += f"后天：{json_data.get('scratch', {}).get('learned', '未知')}  \n"
                markdown_content += f"生活习惯：{json_data.get('scratch', {}).get('lifestyle', '未知')}  \n"
                markdown_content += f"当前状态：{json_data.get('currently', '未知')}\n\n"
            except FileNotFoundError:
                # 缺少 agent.json 时，跳过该人物但不中断流程（减少噪声并避免乱码困扰）
                print(f"[提示] 未找到 {clean_name} 的 agent.json，跳过人物简介。")
                continue
        return markdown_content

    def extract_action(json_data):
        """从存档数据中提取并格式化代理人的活动记录
        json_data: 存档数据
        返回: Markdown格式的活动记录
        """
        markdown_content = ""
        agents = json_data["agents"]  # 获取所有代理人数据
        
        # 遍历每个代理人的数据
        for agent_name, agent_data in agents.items():
            # 清理名称中可能出现的问题
            clean_name = agent_name.replace(" ", "")
            
            # 如果是新出现的代理人,初始化其状态记录
            if clean_name not in last_state.keys():
                last_state[clean_name] = {
                    "currently": "",  # 当前状态
                    "location": "",  # 位置
                    "action": ""  # 动作
                }

            # 获取位置和动作信息
            location = "，".join(agent_data["action"]["event"]["address"])
            action = agent_data["action"]["event"]["describe"]

            # 如果位置和动作都没变,跳过此代理人
            if location == last_state[clean_name]["location"] and action == last_state[clean_name]["action"]:
                continue

            # 更新状态记录
            last_state[clean_name]["location"] = location
            last_state[clean_name]["action"] = action

            # 如果是第一条记录,添加时间标题和活动记录标题
            if len(markdown_content) < 1:
                markdown_content = f"# {json_data['time']}\n\n"  # 添加时间标题
                markdown_content += "## 活动记录：\n\n"  # 添加活动记录标题

            # 添加代理人的活动记录
            markdown_content += f"### {clean_name}\n"  # 代理人名称作为三级标题

            # 如果没有动作描述,默认为睡觉
            if len(action) < 1:
                action = "睡觉"

            # 添加位置和活动信息
            markdown_content += f"位置：{location}  \n"  # 添加位置信息(使用两个空格表示换行)
            markdown_content += f"活动：{action}  \n"  # 添加活动信息
            markdown_content += f"\n"  # 添加空行

        # 如果当前时间点有对话记录,添加对话内容
        if json_data['time'] not in conversation.keys():
            return markdown_content  # 如果没有对话记录,直接返回当前内容

        # 添加对话记录标题
        markdown_content += "## 对话记录：\n\n"
        # 遍历该时间点的所有对话
        for chats in conversation[json_data['time']]:
            for agents, chat in chats.items():
                # 清理对话参与者名称中可能的空格问题
                cleaned_agents = agents.replace(" ", "")
                # 添加对话参与者信息作为三级标题
                markdown_content += f"### {cleaned_agents}\n\n"
                # 添加对话内容,使用Markdown的引用格式
                for item in chat:
                    # 清理名称中可能出现的问题
                    speaker = item[0].replace(" ", "")
                    markdown_content += f"`{speaker}`\n> {item[1]}\n\n"
        return markdown_content

    # 生成基础人设部分
    all_markdown_content = extract_description()
    
    # 遍历所有存档文件,生成活动记录
    files = sorted(os.listdir(checkpoints_folder))
    for file_name in files:
        # 跳过非JSON文件和对话记录文件
        if (not file_name.endswith(".json")) or (file_name == conversation_file):
            continue

        # 读取存档文件并提取活动记录
        file_path = os.path.join(checkpoints_folder, file_name)
        with open(file_path, "r", encoding="utf-8") as f:
            json_data = json.load(f)
            content = extract_action(json_data)  # 提取活动记录
            all_markdown_content += content + "\n\n"  # 添加到总内容中
            
    # 将所有内容写入Markdown文件
    with open(f"{compressed_folder}/{compressed_file}", "w", encoding="utf-8") as compressed_file:
        compressed_file.write(all_markdown_content)


# 创建命令行参数解析器
parser = argparse.ArgumentParser()
parser.add_argument("--name", type=str, default="", help="the name of the simulation")
args = parser.parse_args()


if __name__ == "__main__":
    # 获取模拟名称
    name = args.name
    if len(name) < 1:  # 如果未提供名称,提示用户输入
        name = input("Please enter a simulation name: ")

    # 结果目录根（支持 GA_RESULTS_DIR 与打包运行目录）
    results_root = _results_root()

    # 检查模拟文件夹是否存在
    checkpoints_folder = os.path.join(results_root, "checkpoints", name)
    while not os.path.exists(checkpoints_folder):
        name = input(f"'{name}' doesn't exists, please re-enter the simulation name: ")
        checkpoints_folder = os.path.join(results_root, "checkpoints", name)

    # 设置输入和输出文件夹路径
    compressed_folder = os.path.join(results_root, "compressed", name)  # 压缩文件输出文件夹
    os.makedirs(compressed_folder, exist_ok=True)  # 创建输出文件夹(如果不存在)

    # 生成报告和动作记录
    generate_report(checkpoints_folder, compressed_folder, file_markdown)  # 生成Markdown报告
    generate_movement(checkpoints_folder, compressed_folder, file_movement)  # 生成动作记录