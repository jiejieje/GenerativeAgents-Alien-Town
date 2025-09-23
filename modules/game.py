"""
这个模块实现了游戏的主要逻辑控制:
1. Game类 - 管理整个游戏系统,包括地图、代理人等
2. 提供创建和获取游戏实例的全局函数
"""

import os  # 导入操作系统模块,用于处理文件路径
import copy  # 导入copy模块,用于深度复制对象
import json  # 导入json模块,用于处理JSON数据

# 导入工具类和函数
from modules.utils import GenerativeAgentsMap, GenerativeAgentsKey
from modules import utils
from .maze import Maze  # 导入迷宫类
from .agent import Agent  # 导入代理人类


class Game:
    """游戏主类,管理整个游戏系统"""

    def __init__(self, name, static_root, config, conversation, logger=None):
        """初始化游戏实例
        name: 游戏名称
        static_root: 静态资源根目录
        config: 游戏配置信息
        conversation: 对话系统
        logger: 日志记录器
        """
        self.name = name  # 保存游戏名称
        self.static_root = static_root  # 保存静态资源目录路径
        self.record_iterval = config.get("record_iterval", 30)  # 获取记录间隔,默认30
        self.logger = logger or utils.IOLogger()  # 设置日志记录器,如果未提供则创建新的
        
        # 创建迷宫实例,使用从配置文件加载的迷宫配置
        self.maze = Maze(self.load_static(config["maze"]["path"]), self.logger)
        self.conversation = conversation  # 保存对话系统
        self.agents = {}  # 初始化代理人字典
        
        # 获取代理人基础配置
        if "agent_base" in config:
            agent_base = config["agent_base"]
        else:
            agent_base = {}
            
        # 创建存储根目录
        storage_root = os.path.join(f"results/checkpoints/{name}", "storage")
        if not os.path.isdir(storage_root):
            os.makedirs(storage_root)  # 如果目录不存在则创建
            
        # 创建所有代理人实例
        for agent_name, agent_base_config in config["agents"].items(): # 使用更清晰的变量名
            full_config_path = os.path.join(self.static_root, agent_base_config.get("config_path", ""))
            try:
                # 1. 加载并合并基础配置和特定代理人的配置
                if "config_path" not in agent_base_config:
                     self.logger.warning(f"Agent '{agent_name}' 在 config 中缺少 'config_path'，跳过加载特定配置。")
                     agent_specific_config = {}
                else:
                     agent_specific_config = self.load_static(agent_base_config["config_path"])

                # 合并 agent_base, agent_specific_config, 和 config["agents"][agent_name] 中的其他项
                agent_config = utils.update_dict(copy.deepcopy(agent_base), agent_specific_config)
                agent_config = utils.update_dict(agent_config, agent_base_config) # agent_base_config 包含 config_path 及其他项

                # 在创建 Agent 实例前，将全局的 api_keys 添加到 agent_config 中
                if "api_keys" in config: # 使用传入的全局 config 对象
                    agent_config["api_keys"] = config["api_keys"]
                else:
                    self.logger.warning(f"全局配置中未找到 'api_keys'，Agent '{agent_name}' 可能无法正确初始化需要API密钥的模块。")

                # 2. 设置代理人的存储目录
                agent_config["storage_root"] = os.path.join(storage_root, agent_name)

                # 3. 创建代理人实例并存储到字典中
                self.agents[agent_name] = Agent(agent_config, self.maze, self.conversation, self.logger)
                self.logger.debug(f"成功加载并创建代理人: {agent_name}")

            except FileNotFoundError:
                 self.logger.error(f"错误：代理人 '{agent_name}' 的配置文件未找到于 '{full_config_path}'。已跳过此代理人。")
            except json.JSONDecodeError as e:
                 self.logger.error(f"错误：解析代理人 '{agent_name}' 的 JSON 配置文件 '{full_config_path}' 失败: {e}。已跳过此代理人。")
            except Exception as e:
                 # 捕获其他可能的错误 (例如 Agent 初始化失败)
                 self.logger.error(f"错误：加载或创建代理人 '{agent_name}' 时发生意外错误: {e}。已跳过此代理人。")
                 # 可以在这里添加更详细的错误追踪信息，如果需要
                 # import traceback
                 # self.logger.error(traceback.format_exc())

    def get_agent(self, name):
        """获取指定名称的代理人实例
        name: 代理人名称
        返回: 对应的Agent对象
        """
        return self.agents[name]  # 从代理人字典中返回指定名称的代理人

    def agent_think(self, name, status):
        """让指定的代理人进行思考并返回行动计划和状态信息
        name: 代理人名称
        status: 当前状态信息
        返回: 包含计划和信息的字典
        """
        agent = self.get_agent(name)  # 获取指定的代理人
        plan = agent.think(status, self.agents)  # 让代理人思考并生成计划
        
        # 收集代理人的各种状态信息
        info = {
            "currently": agent.scratch.currently,  # 当前状态
            "associate": agent.associate.abstract(),  # 关联信息的摘要
            "concepts": {c.node_id: c.abstract() for c in agent.concepts},  # 所有概念的摘要
            "chats": [  # 对话记录
                {"name": "self" if n == agent.name else n, "chat": c}  # 标记自己的对话为"self"
                for n, c in agent.chats
            ],
            "action": agent.action.abstract(),  # 行动的摘要
            "schedule": agent.schedule.abstract(),  # 日程的摘要
            "address": agent.get_tile().get_address(as_list=False),  # 当前位置地址
        }
        
        # 检查是否需要记录(基于时间间隔)
        if (
            utils.get_timer().daily_duration() - agent.last_record
        ) > self.record_iterval:
            info["record"] = True  # 需要记录
            agent.last_record = utils.get_timer().daily_duration()  # 更新最后记录时间
        else:
            info["record"] = False  # 不需要记录
            
        # 如果语言模型可用,添加其摘要信息
        if agent.llm_available():
            info["llm"] = agent._llm.get_summary()
            
        # 生成日志标题并记录代理人信息
        title = "{}.summary @ {}".format(
            name, utils.get_timer().get_date("%Y%m%d-%H:%M:%S")  # 包含代理人名称和当前时间
        )
        self.logger.info("\n{}\n{}\n".format(utils.split_line(title), agent))
        
        return {"plan": plan, "info": info}  # 返回计划和信息

    def load_static(self, path):
        """从静态资源目录加载配置文件
        path: 相对于静态资源根目录的文件路径
        返回: 加载的配置字典
        """
        # 将相对路径转换为完整路径并加载字典数据
        return utils.load_dict(os.path.join(self.static_root, path))

    def reset_game(self, keys):
        """重置游戏状态
        keys: 需要重置的键列表
        """
        # 遍历所有代理人进行重置
        for a_name, agent in self.agents.items():
            agent.reset(keys)  # 重置代理人的指定属性
            # 生成重置日志标题
            title = "{}.reset".format(a_name)
            # 记录重置后的代理人状态
            self.logger.info("\n{}\n{}\n".format(utils.split_line(title), agent))


def create_game(name, static_root, config, conversation, logger=None):
    """创建游戏实例的全局函数
    name: 游戏名称
    static_root: 静态资源根目录
    config: 游戏配置
    conversation: 对话系统
    logger: 日志记录器
    返回: 创建的Game实例
    """
    # 使用配置中的时间设置初始化计时器
    utils.set_timer(**config.get("time", {}))
    
    # 创建游戏实例并存储到全局映射中
    GenerativeAgentsMap.set(
        GenerativeAgentsKey.GAME, 
        Game(name, static_root, config, conversation, logger=logger)
    )
    
    # 返回创建的游戏实例
    return GenerativeAgentsMap.get(GenerativeAgentsKey.GAME)


def get_game():
    """获取全局游戏实例的函数
    返回: 全局Game实例
    """
    return GenerativeAgentsMap.get(GenerativeAgentsKey.GAME)
