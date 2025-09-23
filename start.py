"""
这个模块是模拟系统的主入口:
1. 负责创建和管理模拟实例
2. 处理模拟的运行、暂停和恢复
3. 保存模拟过程中的数据
"""

import os  # 导入操作系统模块,用于文件和目录操作
import copy  # 导入复制模块,用于深度复制对象
import json  # 导入json模块,用于处理配置文件
import argparse  # 导入命令行参数解析模块
import datetime  # 导入日期时间处理模块
import sys  # 兼容 PyInstaller 冻结运行时路径

# 强制 UTF-8 日志与 I/O，避免 Windows 控制台编码导致中文乱码
try:
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    os.environ.setdefault("PYTHONUTF8", "1")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from dotenv import load_dotenv, find_dotenv  # 导入环境变量处理模块

from modules.game import create_game, get_game  # 导入游戏创建和获取函数
from modules import utils  # 导入工具函数

# 运行时根目录与资源根目录（兼容 PyInstaller one-folder 的 _internal 布局）
def _get_base_dir():
    if getattr(sys, "frozen", False):
        try:
            return os.path.dirname(sys.executable)
        except Exception:
            pass
    # 源码运行：优先使用脚本所在目录，避免依赖外部工作目录
    return os.path.dirname(os.path.abspath(__file__))


def _get_resource_root(base_dir: str) -> str:
    # 支持多种打包运行目录
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

# 定义模拟中的角色列表
personas = [
    "光谱艺术家",
    "生命研究者",
    "恒星音乐家"
]


class SimulateServer:
    """模拟服务器类,负责管理整个模拟过程"""
    
    def __init__(self, name, static_root, checkpoints_folder, config, start_step=0, verbose="info", log_file=""):
        """初始化模服务器
        name: 模拟实例名称
        static_root: 静态资源根目录
        checkpoints_folder: 存档文件夹路径
        config: 配置信息
        start_step: 起始步数(用于断点恢复)
        verbose: 日志详细程度
        log_file: 日志文件名
        """
        print(f"[SimulateServer.__init__] DEBUG: Initializing for name='{name}'", flush=True)
        self.name = name
        self.static_root = static_root
        self.checkpoints_folder = checkpoints_folder
        
        # 新增：保存绘画记录的目录
        self.paint_records_folder = "results/paint-records"
        # 新增：创建绘画记录目录(如果不存在)
        os.makedirs(self.paint_records_folder, exist_ok=True)

        # 新增：保存音乐记录的目录
        self.music_records_folder = "results/music-records"
        # 新增：创建音乐记录目录(如果不存在)
        os.makedirs(self.music_records_folder, exist_ok=True)

        # 新增：保存量子计算记录的目录
        self.quantum_computing_records_folder = "results/quantum-computing-records"
        # 新增：创建量子计算记录目录(如果不存在)
        os.makedirs(self.quantum_computing_records_folder, exist_ok=True)

        self.config = config
        os.makedirs(checkpoints_folder, exist_ok=True)
        print(f"[SimulateServer.__init__] DEBUG: Checkpoints folder ensured: {checkpoints_folder}", flush=True)

        # 载入历史对话数据(用于断点恢复)
        self.conversation_log = f"{checkpoints_folder}/conversation.json"
        if os.path.exists(self.conversation_log):  # 如果存在对话记录文件
            with open(self.conversation_log, "r", encoding="utf-8") as f:
                conversation = json.load(f)  # 加载历史对话数据
        else:
            conversation = {}  # 否则创建空的对话记录
        print(f"[SimulateServer.__init__] DEBUG: Loading conversation log from: {self.conversation_log}", flush=True)

        # 设置日志记录器
        print(f"[SimulateServer.__init__] DEBUG: Setting up logger (verbose={verbose}, log_file={log_file})...", flush=True)
        if len(log_file) > 0:
            self.logger = utils.create_file_logger(f"{checkpoints_folder}/{log_file}", verbose)
        else:
            self.logger = utils.create_io_logger(verbose)
        print("[SimulateServer.__init__] DEBUG: Logger created.", flush=True)

        # 创建游戏实例
        print("[SimulateServer.__init__] DEBUG: Calling create_game...", flush=True)
        game = create_game(name, static_root, config, conversation, logger=self.logger)
        print("[SimulateServer.__init__] DEBUG: create_game finished.", flush=True)
        print("[SimulateServer.__init__] DEBUG: Calling game.reset_game...", flush=True)
        # Ensure api_keys exists before accessing
        api_keys = config.get("api_keys")
        if not api_keys:
             print("[SimulateServer.__init__] FATAL: 'api_keys' not found in sim_config!", flush=True)
             raise ValueError("API keys are missing in the configuration.")
        game.reset_game(keys=api_keys)
        print("[SimulateServer.__init__] DEBUG: game.reset_game finished.", flush=True)

        # 获取游戏实例并初始化基本属性
        print("[SimulateServer.__init__] DEBUG: Calling get_game...", flush=True)
        self.game = get_game()
        print("[SimulateServer.__init__] DEBUG: get_game finished.", flush=True)
        self.tile_size = self.game.maze.tile_size
        self.agent_status = {}
        print(f"[SimulateServer.__init__] DEBUG: Tile size: {self.tile_size}", flush=True)

        # 获取代理人基础配置
        agent_base = config.get("agent_base", {})
        print("[SimulateServer.__init__] DEBUG: Agent base config obtained.", flush=True)

        # 初始化所有代理人的状态
        print("[SimulateServer.__init__] DEBUG: Starting agent initialization loop...", flush=True)
        agents_to_load = config.get("agents", {})
        print(f"[SimulateServer.__init__] DEBUG: Agents to load: {list(agents_to_load.keys())}", flush=True)
        for agent_name, agent in agents_to_load.items():
            print(f"[SimulateServer.__init__] DEBUG: Processing agent: '{agent_name}'", flush=True)
            # 复制基础配置并更新特定代理人的配置
            agent_config = copy.deepcopy(agent_base)
            config_path = agent.get("config_path")
            if not config_path:
                 print(f"[SimulateServer.__init__] ERROR: 'config_path' missing for agent '{agent_name}' in sim_config!", flush=True)
                 continue # Skip this agent or raise error?
            
            print(f"[SimulateServer.__init__] DEBUG: Loading static config for '{agent_name}' from '{config_path}'...", flush=True)
            try:
                loaded_config = self.load_static(config_path)
                print(f"[SimulateServer.__init__] DEBUG: Static config loaded for '{agent_name}'.", flush=True)
                agent_config.update(loaded_config)
                print(f"[SimulateServer.__init__] DEBUG: Agent config updated for '{agent_name}'.", flush=True)
            except Exception as e:
                print(f"[SimulateServer.__init__] ERROR: Failed to load or update config for agent '{agent_name}' from path '{config_path}': {e}", flush=True)
                # Optionally re-raise or handle differently
                continue # Skip this agent

            # 设置代理人的初始状态
            coord = agent_config.get("coord")
            if coord is None:
                print(f"[SimulateServer.__init__] ERROR: 'coord' missing in final config for agent '{agent_name}' after loading '{config_path}'!", flush=True)
                continue # Skip this agent
                
            self.agent_status[agent_name] = {
                "coord": coord,
                "path": [],
            }
            print(f"[SimulateServer.__init__] DEBUG: Agent '{agent_name}' status initialized with coord: {coord}", flush=True)
        
        # 获取所有代理人中最大的思考间隔作为全局间隔
        print("[SimulateServer.__init__] DEBUG: Calculating max think interval...", flush=True)
        # Check if self.game.agents is populated
        if not self.game.agents:
             print("[SimulateServer.__init__] WARNING: No agents seem to be loaded into the game instance (self.game.agents is empty). Cannot calculate think_interval.", flush=True)
             self.think_interval = 1 # Default or error
        else:
            try:
                self.think_interval = max(
                    a.think_config["interval"] for a in self.game.agents.values()
                )
                print(f"[SimulateServer.__init__] DEBUG: Max think interval set to: {self.think_interval}", flush=True)
            except KeyError as e:
                 print(f"[SimulateServer.__init__] ERROR: Could not calculate think_interval. Agent missing 'think_config' or 'interval': {e}", flush=True)
                 self.think_interval = 1 # Default or error
            except Exception as e:
                 print(f"[SimulateServer.__init__] ERROR: Unexpected error calculating think_interval: {e}", flush=True)
                 self.think_interval = 1 # Default or error

        self.start_step = start_step
        print(f"[SimulateServer.__init__] INFO: SimulateServer initialization finished successfully for '{name}'.", flush=True)

    def simulate(self, step, stride=0):
        """执行模拟
        step: 模拟步数
        stride: 每步的时间间隔(分钟)
        """
        timer = utils.get_timer()  # 获取计时器

        # 执行指定步数的模拟
        for i in range(self.start_step, self.start_step + step):
            # 生成当前步骤的标题(包含步数和时间)
            title = "Simulate Step[{}/{}, time: {}]".format(i+1, self.start_step + step, timer.get_date())
            self.logger.info("\n" + utils.split_line(title, "="))  # 记录步骤信息

            # 让每个代理人思考并执行动作
            for name, status in self.agent_status.items():
                # 获取代理人的思考结果(行动计划)
                plan = self.game.agent_think(name, status)["plan"]
                agent = self.game.get_agent(name)  # 获取代理人实例

                # 确保代理人在配置中存在
                if name not in self.config["agents"]:
                    self.config["agents"][name] = {}
                
                # 更新代理人的配置信息
                self.config["agents"][name].update(agent.to_dict())
                
                # 如果有新的移动路径,更新代理人位置
                if plan.get("path"):
                    status["coord"], status["path"] = plan["path"][-1], []
                
                # 更新配置中的代理人位置信息
                self.config["agents"][name].update(
                    {"coord": status["coord"]}
                )

            # 获取当前模拟时间
            sim_time = timer.get_date("%Y%m%d-%H:%M")
            # 更新配置中的时间和步数信息
            self.config.update(
                {
                    "time": sim_time,
                    "step": i + 1,
                }
            )
            
            # 保存当前步骤的模拟数据
            with open(f"{self.checkpoints_folder}/simulate-{sim_time.replace(':', '')}.json", "w", encoding="utf-8") as f:
                f.write(json.dumps(self.config, indent=2, ensure_ascii=False))
            # 保存对话数据
            with open(f"{self.checkpoints_folder}/conversation.json", "w", encoding="utf-8") as f:
                f.write(json.dumps(self.game.conversation, indent=2, ensure_ascii=False))

            # 如果指定了时间间隔,推进时间
            if stride > 0:
                timer.forward(stride)

            # 新增：保存 painting_records.json 到指定文件
            self.save_painting_records()
            # 新增：保存 music_records.json 到指定文件
            self.save_music_records()
            # 新增：保存 quantum_computing_records.json 到指定文件
            self.save_quantum_computing_records()

    def load_static(self, path):
        """加载静态资源文件
        path: 相对于静态资源根目录的文件路径
        返回: 加载的配置字典
        """
        return utils.load_dict(os.path.join(self.static_root, path))

    def save_painting_records(self):
        """保存 painting_records.json 到以模拟名称命名的文件中（仅当全局文件存在且为非空列表时才写入）"""
        painting_records_file = "results/painting_records.json"
        try:
            painting_records = []
            if os.path.exists(painting_records_file):
                try:
                    with open(painting_records_file, "r", encoding="utf-8") as f:
                        loaded = json.load(f)
                    if isinstance(loaded, list) and len(loaded) > 0:
                        painting_records = loaded
                except Exception:
                    self.logger.info(f"Failed reading {painting_records_file}. Skip generating paint-records for {self.name}.")

            if painting_records:
                target_file = os.path.join(self.paint_records_folder, f"{self.name}.json")
                with open(target_file, "w", encoding="utf-8") as f:
                    json.dump(painting_records, f, indent=2, ensure_ascii=False)
        except Exception as e:
            self.logger.error(f"Error saving painting records for {self.name}: {e}")

    def save_music_records(self):
        """保存 music_records.json 到以模拟名称命名的文件中"""
        music_records_file = "results/music_records.json"
        def _format_time_str(raw):
            try:
                if isinstance(raw, dict):
                    raw = raw.get("start", "")
                if isinstance(raw, str) and len(raw) >= 13:
                    return datetime.datetime.strptime(raw, "%Y%m%d-%H:%M").strftime("%Y-%m-%d %H:%M:%S")
            except Exception:
                pass
            return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # 注意：打包后仅当全局输入文件存在且非空时才生成当前模拟的 music-records，避免误触发音频生成

        try:
            music_records = []
            if os.path.exists(music_records_file):
                try:
                    with open(music_records_file, "r", encoding="utf-8") as f:
                        loaded = json.load(f)
                    if isinstance(loaded, list) and len(loaded) > 0:
                        music_records = loaded
                except Exception:
                    self.logger.info(f"Failed reading {music_records_file}. Skip generating music-records for {self.name}.")

            if music_records:
                target_file = os.path.join(self.music_records_folder, f"{self.name}.json")
                with open(target_file, "w", encoding="utf-8") as f:
                    json.dump(music_records, f, indent=2, ensure_ascii=False)
        except Exception as e:
            self.logger.error(f"Error saving music records for {self.name}: {e}")

    def save_quantum_computing_records(self):
        """保存 quantum_computing_records.json 到以模拟名称命名的文件中"""
        quantum_computing_records_file = "results/quantum_computing_records.json"
        def _format_time_str(raw):
            try:
                if isinstance(raw, dict):
                    raw = raw.get("start", "")
                if isinstance(raw, str) and len(raw) >= 13:
                    return datetime.datetime.strptime(raw, "%Y%m%d-%H:%M").strftime("%Y-%m-%d %H:%M:%S")
            except Exception:
                pass
            return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # 注意：打包后仅当全局输入文件存在且非空时才生成当前模拟的 quantum-computing-records，避免误触发网页生成

        try:
            quantum_records = []
            if os.path.exists(quantum_computing_records_file):
                try:
                    with open(quantum_computing_records_file, "r", encoding="utf-8") as f:
                        loaded = json.load(f)
                    if isinstance(loaded, list) and len(loaded) > 0:
                        quantum_records = loaded
                except Exception:
                    self.logger.info(f"Failed reading {quantum_computing_records_file}. Skip generating quantum-records for {self.name}.")

            if quantum_records:
                target_file = os.path.join(self.quantum_computing_records_folder, f"{self.name}.json")
                with open(target_file, "w", encoding="utf-8") as f:
                    json.dump(quantum_records, f, indent=2, ensure_ascii=False)
        except Exception as e:
            self.logger.error(f"Error saving quantum computing records for {self.name}: {e}")

# 辅助函数部分

def get_config_from_log(checkpoints_folder):
    """从存档数据中加载配置,用于断点恢复
    checkpoints_folder: 存档文件夹路径
    返回: 加载的配置信息,如果没有存档则返回None
    """
    # 获取存档文件夹中的所有文件并排序
    files = sorted(os.listdir(checkpoints_folder))

    # 收集所有JSON存档文件(排除对话记录文件)
    json_files = list()
    for file_name in files:
        if file_name.endswith(".json") and file_name != "conversation.json":
            json_files.append(os.path.join(checkpoints_folder, file_name))

    # 如果没有存档文件,返回None
    if len(json_files) < 1:
        return None

    # 读取最后一个存档文件的配置
    with open(json_files[-1], "r", encoding="utf-8") as f:
        config = json.load(f)

    # 设置资源根目录路径
    assets_root = os.path.join("assets", "village")

    # 计算下一步的开始时间
    start_time = datetime.datetime.strptime(config["time"], "%Y%m%d-%H:%M")
    start_time += datetime.timedelta(minutes=config["stride"])  # 增加一个时间步长
    config["time"] = {"start": start_time.strftime("%Y%m%d-%H:%M")}  # 更新配置中的时间

    # 更新所有代理人的配置文件路径
    agents = config["agents"]
    for a in agents:
        config["agents"][a]["config_path"] = os.path.join(
            assets_root, 
            "agents", 
            a.replace(" ", "_"),  # 替换空格为下划线
            "agent.json"
        )

    return config  # 返回更新后的配置


def get_config(start_time="20240213-09:30", stride=15, agents=None):
    """为新游戏创建配置
    start_time: 开始时间
    stride: 时间步长(分钟)
    agents: 代理人列表
    返回: 新的配置字典
    """
    # 加载基础配置文件 config.json（兼容 _internal）
    with open(os.path.join(RESOURCE_ROOT, "data", "config.json"), "r", encoding="utf-8") as f:
        json_data = json.load(f)

    # 获取代理人基础配置 (现在从 "agent_base" 读取)
    if "agent_base" not in json_data:
        # 如果连 agent_base 都没有，这是个严重的配置错误
        raise KeyError("配置文件 config.json 中缺少 'agent_base' 顶级键。")
    agent_config = json_data["agent_base"] 

    # 确保 chat_iter 和 associate 现在从 agent_config (即 agent_base 的内容) 中获取
    # 或者，如果后续代码期望它们在 json_data 的顶层被重新创建以供其他模块使用，
    # 我们可以这样做 (但这可能不是最佳实践，取决于其他代码如何使用它们)：
    # if "chat_iter" in agent_config:
    #     json_data["chat_iter"] = agent_config["chat_iter"]
    # if "associate" in agent_config:

    # 设置资源根目录路径
    assets_root = os.path.join("assets", "village")
    
    # 创建新的配置字典
    config = {
        "stride": stride,  # 时间步长(分钟)
        "time": {"start": start_time},  # 开始时间
        "maze": {"path": os.path.join(assets_root, "maze.json")},  # 迷宫配置文件路径
        "agent_base": agent_config,  # 代理人基础配置
        "agents": {},  # 代理人具体配置(初始为空)
        "api_keys": json_data["api_keys"],  # API密钥
    }
    
    # 为每个代理人添加配置
    for a in agents:
        config["agents"][a] = {
            "config_path": os.path.join(
                assets_root, 
                "agents", 
                a.replace(" ", "_"),  # 替换空格为下划线
                "agent.json"
            ),
        }
    return config  # 返回完整的配置字典


# 加载环境变量
load_dotenv(find_dotenv())

# 创建命令行参数解析器
parser = argparse.ArgumentParser(description="console for village")
parser.add_argument("--name", type=str, default="", help="The simulation name")  # 模拟名称
parser.add_argument("--start", type=str, default="20240213-09:30", help="The starting time of the simulated ville")  # 开始时间
parser.add_argument("--resume", action="store_true", help="Resume running the simulation")  # 是否继续上次的模拟
parser.add_argument("--step", type=int, default=10, help="The simulate step")  # 模拟步数
parser.add_argument("--stride", type=int, default=10, help="The step stride in minute")  # 每步的时间间隔
parser.add_argument("--verbose", type=str, default="debug", help="The verbose level")  # 日志详细程度
parser.add_argument("--log", type=str, default="", help="Name of the log file")  # 日志文件名
args = parser.parse_args()  # 解析命令行参数


if __name__ == "__main__":
    print("[start.py] INFO: Script started execution.", flush=True)
    # 设置存档根目录
    checkpoints_path = "results/checkpoints"
    print(f"[start.py] DEBUG: Checkpoints path set to: {checkpoints_path}", flush=True)

    # 获取模拟名称
    name = args.name
    print(f"[start.py] DEBUG: Simulation name from args: {name}", flush=True)
    if len(name) < 1: # 如果未提供名称,提示用户输入
        # This block should not be reached when called from creator
        print("[start.py] ERROR: Simulation name is missing! This should not happen when called from creator.", flush=True)
        name = "error_missing_name"
        # exit(1) # Or simply exit

    # 处理继续模拟的情况
    resume = args.resume
    print(f"[start.py] DEBUG: Resume flag: {resume}", flush=True)
    checkpoints_folder = f"{checkpoints_path}/{name}"
    print(f"[start.py] DEBUG: Checkpoints folder: {checkpoints_folder}", flush=True)
    if resume:
        print(f"[start.py] INFO: Attempting to resume simulation '{name}' from {checkpoints_folder}", flush=True)
        # 检查存档是否存在 (仅在 resume 时检查)
        if not os.path.exists(checkpoints_folder):
             print(f"[start.py] ERROR: Checkpoint folder '{checkpoints_folder}' does not exist for resuming.", flush=True)
             sys.exit(1)
        sim_config = get_config_from_log(checkpoints_folder)
        if sim_config is None:
            print(f"[start.py] ERROR: No checkpoint file found in '{checkpoints_folder}' to resume running.", flush=True)
            sys.exit(1)
        start_step = sim_config.get("step", 0) # Safely get step
        print(f"[start.py] DEBUG: Resuming from step {start_step}", flush=True)
    else:
        print(f"[start.py] INFO: Preparing new simulation '{name}'. Clearing global record files.", flush=True)
        
        # 定义全局记录文件的路径 (相对于 start.py)
        music_records_file_to_clear = "results/music_records.json"
        painting_records_file_to_clear = "results/painting_records.json"
        quantum_computing_records_file_to_clear = "results/quantum_computing_records.json"
        base_results_dir = "results" # 这些文件所在的目录

        # 确保 'results' 目录存在，如果不存在则创建
        os.makedirs(base_results_dir, exist_ok=True)

        try:
            with open(music_records_file_to_clear, "w", encoding="utf-8") as f_music:
                json.dump([], f_music)
            print(f"[start.py] INFO: Successfully cleared '{music_records_file_to_clear}'.", flush=True)
        except Exception as e_music:
            print(f"[start.py] WARNING: Failed to clear '{music_records_file_to_clear}': {e_music}", flush=True)

        try:
            with open(painting_records_file_to_clear, "w", encoding="utf-8") as f_paint:
                json.dump([], f_paint)
            print(f"[start.py] INFO: Successfully cleared '{painting_records_file_to_clear}'.", flush=True)
        except Exception as e_paint:
            print(f"[start.py] WARNING: Failed to clear '{painting_records_file_to_clear}': {e_paint}", flush=True)
        
        # 新增：清空量子计算记录文件
        try:
            with open(quantum_computing_records_file_to_clear, "w", encoding="utf-8") as f_quantum:
                json.dump([], f_quantum)
            print(f"[start.py] INFO: Successfully cleared '{quantum_computing_records_file_to_clear}'.", flush=True)
        except Exception as e_quantum:
            print(f"[start.py] WARNING: Failed to clear '{quantum_computing_records_file_to_clear}': {e_quantum}", flush=True)

        # 如果存在 UI 选择结果，则覆盖 personas 列表
        try:
            sel_file = os.path.join(BASE_DIR, "results", "selected_personas.json")
            if os.path.exists(sel_file):
                with open(sel_file, "r", encoding="utf-8") as f_sel:
                    selected = json.load(f_sel)
                if isinstance(selected, list) and selected:
                    globals()["personas"] = selected
                    print(f"[start.py] INFO: Loaded selected personas from {sel_file}: {len(selected)}", flush=True)
        except Exception as e_sel:
            print(f"[start.py] WARNING: Failed to read selected personas: {e_sel}", flush=True)

        print("[start.py] DEBUG: Getting new config...", flush=True)
        # Ensure personas list is not empty or handle appropriately
        if not personas:
             print("[start.py] ERROR: Personas list is empty in start.py! Cannot start simulation.", flush=True)
             sys.exit(1)
        sim_config = get_config(args.start, args.stride, personas)
        start_step = 0
        print(f"[start.py] DEBUG: Starting from step {start_step}", flush=True)

    # 设置静态资源目录（兼容 _internal）
    static_root = os.path.join(RESOURCE_ROOT, "frontend", "static")
    print(f"[start.py] DEBUG: Static root set to: {static_root}", flush=True)

    # 创建并运行模拟服务器
    print("[start.py] INFO: Creating SimulateServer instance...", flush=True)
    try:
        server = SimulateServer(name, static_root, checkpoints_folder, sim_config, start_step, args.verbose, args.log)
        print("[start.py] INFO: SimulateServer instance created successfully.", flush=True)
    except Exception as e:
        print(f"[start.py] FATAL: Failed to create SimulateServer instance: {e}", flush=True)
        import traceback
        traceback.print_exc() # Print full traceback
        sys.exit(1)

    print("[start.py] INFO: Starting simulation loop...", flush=True)
    try:
        server.simulate(args.step, args.stride)
        print("[start.py] INFO: Simulation loop finished.", flush=True)
    except Exception as e:
        print(f"[start.py] FATAL: Error during simulation: {e}", flush=True)
        import traceback
        traceback.print_exc() # Print full traceback
        sys.exit(1)

    print("[start.py] INFO: Simulation ended gracefully.", flush=True)
