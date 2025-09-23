"""generative_agents.prompt.scratch
这个模块实现了Scratch类,用于生成和处理各种提示(prompts)。
主要功能包括:
- 构建提示模板
- 处理事件和对话
- 生成行为描述
- 反思和总结
"""

import random  # 导入随机数模块
import datetime  # 导入日期时间模块
import re  # 导入正则表达式模块
from string import Template  # 导入字符串模板类
import os
import sys

from modules import utils  # 导入工具函数模块
from modules.memory import Event  # 导入事件类
from modules.model import parse_llm_output  # 导入LLM输出解析函数


def _get_base_dir():
    if getattr(sys, "frozen", False):
        try:
            return os.path.dirname(sys.executable)
        except Exception:
            pass
    # 源码运行：优先使用模块文件所在目录
    return os.path.dirname(os.path.abspath(__file__))


def _get_resource_root(base_dir: str) -> str:
    # 兼容源码结构：modules/prompt/../../ -> generative_agents
    ga_root = os.path.abspath(os.path.join(base_dir, "..", ".."))
    candidates = [
        base_dir,
        ga_root,
        os.path.join(ga_root, "_internal"),
        os.path.join(ga_root, "AI-Town"),
        os.path.join(ga_root, "AI-Town", "_internal"),
        os.path.join(base_dir, "_internal"),
        os.path.join(base_dir, "AI-Town"),
        os.path.join(base_dir, "AI-Town", "_internal"),
        os.path.join(os.path.dirname(base_dir), "_internal"),
        os.path.join(os.path.dirname(base_dir), "AI-Town", "_internal"),
    ]
    for root in candidates:
        try:
            if os.path.isdir(os.path.join(root, "data")) and os.path.isdir(os.path.join(root, "frontend", "static")):
                return root
        except Exception:
            pass
    return ga_root if os.path.isdir(ga_root) else base_dir


RESOURCE_ROOT = _get_resource_root(_get_base_dir())


class Scratch:
    def __init__(self, name, currently, config):
        """初始化Scratch对象
        Args:
            name: 代理的名字
            currently: 当前状态
            config: 配置信息
        """
        self.name = name  # 存储代理名字
        self.currently = currently  # 存储当前状态
        self.config = config  # 存储配置信息
        # 提示模板目录（兼容 PyInstaller one-folder 布局）
        self.template_path = os.path.join(RESOURCE_ROOT, "data", "prompts")

    def build_prompt(self, template, data):
        """构建提示文本
        Args:
            template: 模板名称
            data: 用于填充模板的数据
        Returns:
            填充后的提示文本
        """
        with open(f"{self.template_path}/{template}.txt", "r", encoding="utf-8") as file:  # 打开模板文件
            file_content = file.read()  # 读取文件内容

        template = Template(file_content)  # 创建字符串模板对象
        filled_content = template.substitute(data)  # 用数据填充模板

        return filled_content  # 返回填充后的内容

    def _base_desc(self):
        """生成基础描述
        Returns:
            包含代理基本信息的描述文本
        """
        return self.build_prompt(
            "base_desc",  # 使用base_desc模板
            {
                "name": self.name,  # 代理名字
                "age": self.config["age"],  # 年龄
                "innate": self.config["innate"],  # 天生特质
                "learned": self.config["learned"],  # 学习特质
                "lifestyle": self.config["lifestyle"],  # 生活方式
                "daily_plan": self.config["daily_plan"],  # 每日计划
                "date": utils.get_timer().daily_format_cn(),  # 当前日期(中文格式)
                "currently": self.currently,  # 当前状态
            }
        )

    def prompt_poignancy_event(self, event):
        """生成评估事件重要性的提示
        Args:
            event: 需要评估的事件对象
        Returns:
            包含提示、回调函数和默认值的字典
        """
        prompt = self.build_prompt(
            "poignancy_event",  # 使用事件重要性评估模板
            {
                "base_desc": self._base_desc(),  # 获取基础描述
                "agent": self.name,  # 代理名字
                "event": event.get_describe(),  # 获取事件描述
            }
        )

        def _callback(response):
            """解析LLM响应获取重要性评分
            Args:
                response: LLM的响应文本
            Returns:
                解析出的重要性评分(1-10的整数)
            """
            pattern = [
                r"评分[:： ]+(\d{1,2})",  # 匹配"评分: 数字"格式
                "(\d{1,2})",  # 匹配纯数字格式
            ]
            return int(parse_llm_output(response, pattern, "match_last"))  # 返回匹配到的最后一个数字

        return {
            "prompt": prompt,  # 提示文本
            "callback": _callback,  # 回调函数
            "failsafe": random.choice(list(range(10))) + 1,  # 默认随机返回1-10的数字
        }

    def prompt_poignancy_chat(self, event):
        """生成评估对话重要性的提示
        Args:
            event: 需要评估的对话事件
        Returns:
            包含提示、回调函数和默认值的字典
        """
        prompt = self.build_prompt(
            "poignancy_chat",  # 使用对话重要性评估模板
            {
                "base_desc": self._base_desc(),  # 获取基础描述
                "agent": self.name,  # 代理名字
                "event": event.get_describe(),  # 获取事件描述
            }
        )

        def _callback(response):
            """解析LLM响应获取重要性评分
            Args:
                response: LLM的响应文本
            Returns:
                解析出的重要性评分(1-10的整数)
            """
            pattern = [
                r"评分[:： ]+(\d{1,2})",  # 匹配"评分: 数字"格式
                "(\d{1,2})",  # 匹配纯数字格式
            ]
            return int(parse_llm_output(response, pattern, "match_last"))  # 返回匹配到的最后一个数字

        return {
            "prompt": prompt,  # 提示文本
            "callback": _callback,  # 回调函数
            "failsafe": random.choice(list(range(10))) + 1,  # 默认随机返回1-10的数字
        }

    def prompt_wake_up(self):
        """生成确定起床时间的提示
        Returns:
            包含提示、回调函数和默认值的字典
        """
        prompt = self.build_prompt(
            "wake_up",  # 使用wake_up模板
            {
                "base_desc": self._base_desc(),  # 获取基础描述
                "lifestyle": self.config["lifestyle"],  # 生活方式
                "agent": self.name,  # 代理名字
            }
        )

        def _callback(response):
            """解析LLM响应获取起床时间
            Args:
                response: LLM的响应文本
            Returns:
                解析出的起床时间(0-11的整数,表示小时)
            """
            patterns = [
                r"(\d{1,2}):00",  # 匹配"小时:00"格式
                r"(\d{1,2})",  # 匹配纯数字格式
                r"\d{1,2}",  # 匹配任意数字
            ]
            wake_up_time = int(parse_llm_output(response, patterns))  # 解析起床时间
            if wake_up_time > 11:  # 如果超过11点
                wake_up_time = 11  # 限制最晚起床时间为11点
            return wake_up_time

        return {"prompt": prompt, "callback": _callback, "failsafe": 6}  # 默认6点起床

    def prompt_schedule_init(self, wake_up):
        """生成初始化日程安排的提示
        Args:
            wake_up: 起床时间(小时)
        Returns:
            包含提示、回调函数和默认值的字典
        """
        prompt = self.build_prompt(
            "schedule_init",  # 使用schedule_init模板
            {
                "base_desc": self._base_desc(),  # 获取基础描述
                "lifestyle": self.config["lifestyle"],  # 生活方式
                "agent": self.name,  # 代理名字
                "wake_up": wake_up,  # 起床时间
            }
        )

        def _callback(response):
            """解析LLM响应获取日程安排列表
            Args:
                response: LLM的响应文本
            Returns:
                解析出的日程安排列表
            """
            patterns = [
                r"\d{1,2}\. (.*)。",  # 匹配"数字. 内容。"格式
                r"\d{1,2}\. (.*)",  # 匹配"数字. 内容"格式
                r"\d{1,2}\) (.*)。",  # 匹配"数字) 内容。"格式
                r"\d{1,2}\) (.*)",  # 匹配"数字) 内容"格式
                r"(.*)。",  # 匹配"内容。"格式
                r"(.*)",  # 匹配任意内容
            ]
            return parse_llm_output(response, patterns, mode="match_all")  # 返回所有匹配的日程

        # 默认的日程安排
        failsafe = [
            "早上6点起床并完成早餐的例行工作",
            "早上7点吃早餐",
            "早上8点看书",
            "中午12点吃午饭",
            "下午1点小睡一会儿",
            "晚上7点放松一下，看电视",
            "晚上11点睡觉",
        ]
        return {"prompt": prompt, "callback": _callback, "failsafe": failsafe}

    def prompt_schedule_daily(self, wake_up, daily_schedule):
        """生成每日具体时间表的提示
        Args:
            wake_up: 起床时间(小时)
            daily_schedule: 日程安排列表
        Returns:
            包含提示、回调函数和默认值的字典
        """
        hourly_schedule = ""  # 初始化小时时间表字符串
        for i in range(wake_up):  # 起床前的时间
            hourly_schedule += f"[{i}:00] 睡觉\n"  # 标记为睡觉时间
        for i in range(wake_up, 24):  # 起床后到一天结束
            hourly_schedule += f"[{i}:00] <活动>\n"  # 标记为待安排活动

        prompt = self.build_prompt(
            "schedule_daily",  # 使用每日时间表模板
            {
                "base_desc": self._base_desc(),  # 获取基础描述
                "agent": self.name,  # 代理名字
                "daily_schedule": "；".join(daily_schedule),  # 将日程列表转换为字符串
                "hourly_schedule": hourly_schedule,  # 小时时间表
            }
        )

        # 默认的每小时活动安排
        failsafe = {
            "6:00": "起床并完成早晨的例行工作",
            "7:00": "吃早餐",
            "8:00": "读书",
            "9:00": "读书",
            "10:00": "读书",
            "11:00": "读书",
            "12:00": "吃午饭",
            "13:00": "小睡一会儿",
            "14:00": "小睡一会儿",
            "15:00": "小睡一会儿",
            "16:00": "继续工作",
            "17:00": "继续工作",
            "18:00": "回家",
            "19:00": "放松，看电视",
            "20:00": "放松，看电视",
            "21:00": "睡前看书",
            "22:00": "准备睡觉",
            "23:00": "睡觉",
        }

        def _callback(response):
            """解析LLM响应获取每小时活动安排
            Args:
                response: LLM的响应文本
            Returns:
                解析出的时间-活动字典
            """
            patterns = [
                r"\[(\d{1,2}:\d{2})\] " + self.name + r"(.*)。",  # 匹配"[时间] 名字活动。"格式
                r"\[(\d{1,2}:\d{2})\] " + self.name + r"(.*)",  # 匹配"[时间] 名字活动"格式
                r"\[(\d{1,2}:\d{2})\] " + r"(.*)。",  # 匹配"[时间] 活动。"格式
                r"\[(\d{1,2}:\d{2})\] " + r"(.*)",  # 匹配"[时间] 活动"格式
            ]
            outputs = parse_llm_output(response, patterns, mode="match_all")  # 获取所有匹配项
            assert len(outputs) >= 5, "less than 5 schedules"  # 确保至少有5个时间段的安排
            return {s[0]: s[1] for s in outputs}  # 返回时间-活动字典

        return {"prompt": prompt, "callback": _callback, "failsafe": failsafe}

    def prompt_schedule_decompose(self, plan, schedule):
        """将计划分解为更细粒度的子计划
        Args:
            plan: 需要分解的计划对象
            schedule: 日程表对象
        Returns:
            包含提示、回调函数和默认值的字典
        """
        def _plan_des(plan):
            """生成计划的描述文本
            Args:
                plan: 计划对象
            Returns:
                格式化的计划描述字符串
            """
            start, end = schedule.plan_stamps(plan, time_format="%H:%M")  # 获取计划的开始和结束时间
            return f'{start} 至 {end}，{self.name} 计划 {plan["describe"]}'  # 返回格式化的描述

        # 获取计划前后的上下文计划索引
        indices = range(
            max(plan["idx"] - 1, 0),  # 从当前计划的前一个开始(如果存在)
            min(plan["idx"] + 2, len(schedule.daily_schedule))  # 到当前计划的后一个结束(如果存在)
        )

        start, end = schedule.plan_stamps(plan, time_format="%H:%M")  # 获取当前计划的时间范围
        increment = max(int(plan["duration"] / 100) * 5, 5)  # 计算时间增量,最小为5分钟

        prompt = self.build_prompt(
            "schedule_decompose",  # 使用计划分解模板
            {
                "base_desc": self._base_desc(),  # 获取基础描述
                "agent": self.name,  # 代理名字
                "plan": "；".join([_plan_des(schedule.daily_schedule[i]) for i in indices]),  # 计划上下文
                "increment": increment,  # 时间增量
                "start": start,  # 开始时间
                "end": end,  # 结束时间
            }
        )

        def _callback(response):
            """解析LLM响应获取分解后的子计划列表
            Args:
                response: LLM的响应文本
            Returns:
                分解后的(描述,持续时间)元组列表
            """
            patterns = [
                r"\d{1,2}\) .*\*计划\* (.*)[\(（]+耗时[:： ]+(\d{1,2})[,， ]+剩余[:： ]+\d*[\)）]",  # 匹配计划描述和时长
            ]
            schedules = parse_llm_output(response, patterns, mode="match_all")  # 获取所有匹配的计划
            schedules = [(s[0].strip("."), int(s[1])) for s in schedules]  # 处理每个计划的描述和时长
            left = plan["duration"] - sum([s[1] for s in schedules])  # 计算剩余时间
            if left > 0:  # 如果还有剩余时间
                schedules.append((plan["describe"], left))  # 添加一个使用剩余时间的计划
            return schedules

        # 默认的分解方案:将计划平均分成多个10分钟的子计划
        failsafe = [(plan["describe"], 10) for _ in range(int(plan["duration"] / 10))]
        return {"prompt": prompt, "callback": _callback, "failsafe": failsafe}

    def prompt_schedule_revise(self, action, schedule):
        """修改日程安排以适应新的活动
        Args:
            action: 需要插入的新活动
            schedule: 日程表对象
        Returns:
            包含提示、回调函数和默认值的字典
        """
        plan, _ = schedule.current_plan()  # 获取当前计划
        start, end = schedule.plan_stamps(plan, time_format="%H:%M")  # 获取计划的时间范围
        act_start_minutes = utils.daily_duration(action.start)  # 获取活动开始时间(分钟)
        original_plan, new_plan = [], []  # 初始化原计划和新计划列表

        def _plan_des(start, end, describe):
            """生成计划的描述文本
            Args:
                start: 开始时间
                end: 结束时间
                describe: 计划描述
            Returns:
                格式化的计划描述字符串
            """
            if not isinstance(start, str):  # 如果时间不是字符串
                start = start.strftime("%H:%M")  # 转换为时间字符串
            if not isinstance(end, str):
                end = end.strftime("%H:%M")
            return "[{} 至 {}] {}".format(start, end, describe)  # 返回格式化的描述

        # 处理原计划和新计划
        for de_plan in plan["decompose"]:  # 遍历分解后的子计划
            de_start, de_end = schedule.plan_stamps(de_plan, time_format="%H:%M")  # 获取子计划时间范围
            original_plan.append(_plan_des(de_start, de_end, de_plan["describe"]))  # 添加到原计划列表
            
            if de_plan["start"] + de_plan["duration"] <= act_start_minutes:  # 如果子计划在新活动之前结束
                new_plan.append(_plan_des(de_start, de_end, de_plan["describe"]))  # 保持不变
            elif de_plan["start"] <= act_start_minutes:  # 如果子计划与新活动有重叠
                new_plan.extend([  # 将子计划分成两部分
                    _plan_des(de_start, action.start, de_plan["describe"]),  # 新活动前的部分
                    _plan_des(action.start, action.end, action.event.get_describe(False)),  # 新活动
                ])

        original_plan, new_plan = "\n".join(original_plan), "\n".join(new_plan)  # 转换为字符串

        prompt = self.build_prompt(
            "schedule_revise",  # 使用日程修改模板
            {
                "agent": self.name,  # 代理名字
                "start": start,  # 开始时间
                "end": end,  # 结束时间
                "original_plan": original_plan,  # 原计划
                "duration": action.duration,  # 新活动持续时间
                "event": action.event.get_describe(),  # 新活动描述
                "new_plan": new_plan,  # 新计划
            }
        )

        def _callback(response):
            """解析LLM响应获取修改后的计划列表
            Args:
                response: LLM的响应文本
            Returns:
                修改后的计划列表
            """
            patterns = [
                r"^\[(\d{1,2}:\d{1,2}) ?- ?(\d{1,2}:\d{1,2})\] (.*)",  # 匹配使用"-"的时间格式
                r"^\[(\d{1,2}:\d{1,2}) ?~ ?(\d{1,2}:\d{1,2})\] (.*)",  # 匹配使用"~"的时间格式
                r"^\[(\d{1,2}:\d{1,2}) ?至 ?(\d{1,2}:\d{1,2})\] (.*)",  # 匹配使用"至"的时间格式
            ]
            schedules = parse_llm_output(response, patterns, mode="match_all")  # 获取所有匹配的计划
            decompose = []  # 初始化分解后的计划列表
            for start, end, describe in schedules:  # 处理每个计划
                m_start = utils.daily_duration(utils.to_date(start, "%H:%M"))  # 转换开始时间为分钟
                m_end = utils.daily_duration(utils.to_date(end, "%H:%M"))  # 转换结束时间为分钟
                decompose.append(  # 添加到分解列表
                    {
                        "idx": len(decompose),  # 计索引
                        "describe": describe,  # 计划描述
                        "start": m_start,  # 开始时间(分钟)
                        "duration": m_end - m_start,  # 持续时间(分钟)
                    }
                )
            return decompose

        return {"prompt": prompt, "callback": _callback, "failsafe": plan["decompose"]}  # 默认返回原计划

    def prompt_determine_sector(self, describes, spatial, address, tile):
        """确定代理下一步要去的区域
        Args:
            describes: 计划描述元组(完整计划,分解计划)
            spatial: 空间对象,包含区域信息
            address: 目标地址
            tile: 当前位置对象
        Returns:
            包含提示、回调函数和默认值的字典
        """
        live_address = spatial.find_address("living_area", as_list=True)[:-1]  # 获取生活区域地址
        curr_address = tile.get_address("sector", as_list=True)  # 获取当前位置地址

        prompt = self.build_prompt(
            "determine_sector",  # 使用区域确定模板
            {
                "agent": self.name,  # 代理名字
                "live_sector": live_address[-1],  # 生活区域名称
                "live_arenas": ", ".join(i for i in spatial.get_leaves(live_address)),  # 生活区域内的场所列表
                "current_sector": curr_address[-1],  # 当前区域名称
                "current_arenas": ", ".join(i for i in spatial.get_leaves(curr_address)),  # 当前区域内的场所列表
                "daily_plan": self.config["daily_plan"],  # 每日计划
                "areas": ", ".join(i for i in spatial.get_leaves(address)),  # 目标地址内的场所列表
                "complete_plan": describes[0],  # 完整计划描述
                "decomposed_plan": describes[1],  # 分解后的计划描述
            }
        )

        sectors = spatial.get_leaves(address)  # 获取目标地址下的所有区域
        arenas = {}  # 初始化场所-区域映射字典
        for sec in sectors:  # 遍历每个区域
            arenas.update(
                {a: sec for a in spatial.get_leaves(address + [sec]) if a not in arenas}  # 建立场所到区域的映射
            )
        failsafe = random.choice(sectors)  # 默认随机选择一个区域

        def _callback(response):
            """解析LLM响应获取选择的区域
            Args:
                response: LLM的响应文本
            Returns:
                选择的区域名称
            """
            patterns = [
                r".*应该去[:： ]*(.*)。",  # 匹配"应该去: xxx。"格式
                r".*应该去[:： ]*(.*)",  # 匹配"应该去: xxx"格式
                r"(.+)。",  # 匹配任意内容加句号
                r"(.+)",  # 匹配任意内容
            ]
            sector = parse_llm_output(response, patterns)  # 解析出区域名称
            if sector in sectors:  # 如果直接匹配到区域名
                return sector
            if sector in arenas:  # 如果匹配到场所名
                return arenas[sector]  # 返回对应的区域
            for s in sectors:  # 遍所有区域
                if sector.startswith(s):  # 如果响应以某个区域名开头
                    return s
            return failsafe  # 都不匹配则返回默认值

        return {"prompt": prompt, "callback": _callback, "failsafe": failsafe}

    def prompt_determine_arena(self, describes, spatial, address):
        """确定代理在特定区域内要去的具体场所
        Args:
            describes: 计划描述元组(完整计划,分解计划)
            spatial: 空间对象,包含区域信息
            address: 目标地址(包含区域信息)
        Returns:
            包含提示、回调函数和默认值的字典
        """
        prompt = self.build_prompt(
            "determine_arena",  # 使用场所确定模板
            {
                "agent": self.name,  # 代理名字
                "target_sector": address[-1],  # 目标区域名称
                "target_arenas": ", ".join(i for i in spatial.get_leaves(address)),  # 区域内的所有场所列表
                "daily_plan": self.config["daily_plan"],  # 每日计划
                "complete_plan": describes[0],  # 完整计划描述
                "decomposed_plan": describes[1],  # 分解后的计划描述
            }
        )

        arenas = spatial.get_leaves(address)  # 获区域内所有可用场所
        failsafe = random.choice(arenas)  # 默认随机选择一个场所

        def _callback(response):
            """解析LLM响应获取选择的场所
            Args:
                response: LLM的响应文本
            Returns:
                选择的场所名称
            """
            patterns = [
                r".*应该去[:： ]*(.*)。",  # 匹配"应该去: xxx。"格式
                r".*应该去[:： ]*(.*)",  # 匹配"应该去: xxx"格式
                r"(.+)。",  # 匹配任意内容加句号
                r"(.+)",  # 匹配任意内容
            ]
            arena = parse_llm_output(response, patterns)  # 解析出场所名称
            return arena if arena in arenas else failsafe  # 如果匹配到有效场所则返回,否则返回默认值

        return {"prompt": prompt, "callback": _callback, "failsafe": failsafe}

    def prompt_determine_object(self, describes, spatial, address):
        """确定代理要与之互动的具体对象
        Args:
            describes: 计划描述元组(完整计划,分解计划)
            spatial: 空间对象,包含区域信息
            address: 目标地址(包含场所信息)
        Returns:
            包含提示、回调函数和默认值的字典
        """
        objects = spatial.get_leaves(address)  # 获取场所内所有可用对象

        prompt = self.build_prompt(
            "determine_object",  # 使用对象确定模板
            {
                "activity": describes[1],  # 分解后的计划描述
                "objects": ", ".join(objects),  # 可用对象列表
            }
        )

        failsafe = random.choice(objects)  # 默认随机选择一个对象

        def _callback(response):
            """解析LLM响应获取选择的对象
            Args:
                response: LLM的响应文本
            Returns:
                选择的对象名称
            """
            patterns = [
                r".*是[:： ]*(.*)。",  # 匹配"是: xxx。"格式
                r".*是[:： ]*(.*)",  # 匹配"是: xxx"格式
                r"(.+)。",  # 匹配任意内容加句号
                r"(.+)",  # 匹配任意内容
            ]
            obj = parse_llm_output(response, patterns)  # 解析出对象名称
            return obj if obj in objects else failsafe  # 如果匹配到有效对象则返回,否则返回默认值

        return {"prompt": prompt, "callback": _callback, "failsafe": failsafe}

    def prompt_describe_emoji(self, describe):
        """为事件描述生成表情符号
        Args:
            describe: 事件描述文本
        Returns:
            包含提示、回调函数和默认值的字典
        """
        prompt = self.build_prompt(
            "describe_emoji",  # 使用表情符号生成模板
            {
                "action": describe,  # 事件描述
            }
        )

        def _callback(response):
            """解析LLM响应获取表情符号
            Args:
                response: LLM的响应文本
            Returns:
                表情符号字符串(最多3个)
            """
            # 正则表达式：匹配大数emoji
            emoji_pattern = u"([\U0001F600-\U0001F64F]|"   # 表情符号
            emoji_pattern += u"[\U0001F300-\U0001F5FF]|"   # 符号和图标
            emoji_pattern += u"[\U0001F680-\U0001F6FF]|"   # 运输和地图符号
            emoji_pattern += u"[\U0001F700-\U0001F77F]|"   # 午夜符号
            emoji_pattern += u"[\U0001F780-\U0001F7FF]|"   # 英镑符号
            emoji_pattern += u"[\U0001F800-\U0001F8FF]|"   # 合成扩展
            emoji_pattern += u"[\U0001F900-\U0001F9FF]|"   # 补充符号和图标
            emoji_pattern += u"[\U0001FA00-\U0001FA6F]|"   # 补充符号和图标
            emoji_pattern += u"[\U0001FA70-\U0001FAFF]|"   # 补充符号和图标
            emoji_pattern += u"[\U00002702-\U000027B0]+)"  # 杂项符号

            emoji = re.compile(emoji_pattern, flags=re.UNICODE).findall(response)  # 查找所有表情符号
            if len(emoji) > 0:  # 如果找到表情符号
                response = "Emoji: " + "".join(i for i in emoji)  # 拼接表情符号
            else:
                response = ""  # 没找到则返回空字符串

            return parse_llm_output(response, ["Emoji: (.*)"])[:3]  # 返回最多3个表情符号

        return {"prompt": prompt, "callback": _callback, "failsafe": "", "retry": 1}  # 默认返回思考表情

    def prompt_describe_event(self, subject, describe, address, emoji=None):
        """生成事件的标准描述
        Args:
            subject: 事件主体(代理名字)
            describe: 原始事件描述
            address: 事件发生地址
            emoji: 相关表情符号
        Returns:
            包含提示、回调函数和默认值的字典
        """
        prompt = self.build_prompt(
            "describe_event",  # 使用事件描述模板
            {
                "action": describe,  # 原始描述
            }
        )

        # 处理原始描述文本,移除特殊字符
        e_describe = describe.replace("(", "").replace(")", "").replace("<", "").replace(">", "")
        if e_describe.startswith(subject + "此时"):  # 如果描述以"主体此时"开头
            e_describe = e_describe.replace(subject + "此时", "")  # 移除这部分
        # 创建默认的事件对象
        failsafe = Event(
            subject, "此时", e_describe, describe=describe, address=address, emoji=emoji
        )

        def _callback(response):
            """解析LLM响应获取标准化的事件描述
            Args:
                response: LLM的响应文本
            Returns:
                Event对象,包含主体、动作和对象
            """
            response_list = response.replace(")", ")\n").split("\n")  # 按行分割响应文本
            for response in response_list:  # 遍历每一行
                if len(response.strip()) < 7:  # 跳过过短的行
                    continue
                # 跳过包含多个括号的行(可能是格式错误)
                if response.count("(") > 1 or response.count(")") > 1 or response.count("（") > 1 or response.count("）") > 1:
                    continue

                patterns = [
                    r"[\(（]<(.+?)>[,， ]+<(.+?)>[,， ]+<(.*)>[\)）]",  # 匹配"(<xxx>, <xxx>, <xxx>)"格式
                    r"[\(（](.+?)[,， ]+(.+?)[,， ]+(.*)[\)）]",  # 匹配"(xxx, xxx, xxx)"格式
                ]
                outputs = parse_llm_output(response, patterns)  # 解析出主体、动作和对象
                if len(outputs) == 3:  # 如果成功解析出三个部分
                    return Event(*outputs, describe=describe, address=address, emoji=emoji)  # 创建并返回事件对象

            return None  # 如果没有找到有效格式,返回None

        return {"prompt": prompt, "callback": _callback, "failsafe": failsafe}

    def prompt_describe_object(self, obj, describe):
        """生成对象状态的描述
        Args:
            obj: 对象名称
            describe: 相关事件描述
        Returns:
            包含提示、回调函数和默认值的字典
        """
        prompt = self.build_prompt(
            "describe_object",  # 使用对象描述模板
            {
                "object": obj,  # 对象名称
                "agent": self.name,  # 代理名字
                "action": describe,  # 事件描述
            }
        )

        def _callback(response):
            """解析LLM响应获取对象状态描述
            Args:
                response: LLM的响应文本
            Returns:
                对象状态描述文本
            """
            print(f"DEBUG: Raw LLM response for describe_object (object: {obj}):\n{response}") # 添加这行来打印原始响应
            patterns = [
                r"<" + obj + r"> ?(.*)。",  # 匹配"<对象>描述。"格式
                r"<" + obj + r"> ?(.*)",  # 匹配"<对象>描述"格式
            ]
            return parse_llm_output(response, patterns)  # 返回解析出的描述

        return {"prompt": prompt, "callback": _callback, "failsafe": "空闲"}  # 默认返回"空闲"状态

    def prompt_decide_chat(self, agent, other, focus, chats):
        """决定是否要与其他代对话
        Args:
            agent: 当前代理对象
            other: 其他代理对象
            focus: 关注点信息字典
            chats: 历史对话记录列表
        Returns:
            包含提示、回调函数和默认值的字典
        """
        def _status_des(a):
            """生成代理状态描述
            Args:
                a: 代理对象
            Returns:
                状态描述文本
            """
            event = a.get_event()  # 获取代理当前事件
            if a.path:  # 如果代理正在移动
                return f"{a.name} 正去往 {event.get_describe(False)}"  # 返回移动状态描述
            return event.get_describe()  # 返回当前事件描述

        # 继续prompt_decide_chat方法
        context = "。".join(
            [c.describe for c in focus["events"]]  # 获取关注的事件描述
        )
        context += "\n" + "。".join([c.describe for c in focus["thoughts"]])  # 添加关注的想法描述
        date_str = utils.get_timer().get_date("%Y-%m-%d %H:%M:%S")  # 获取当前时间字符串
        chat_history = ""  # 初始化对话历史字符串
        if chats:  # 如果有历史对话记录
            chat_history = f" {agent.name} 和 {other.name} 上次在 {chats[0].create} 聊过关于 {chats[0].describe} 的话题"  # 生成上次对话描述
        a_des, o_des = _status_des(agent), _status_des(other)  # 获取两个代理的当前状态描述

        prompt = self.build_prompt(
            "decide_chat",  # 使用对话决策模板
            {
                "context": context,  # 关注点上下文
                "date": date_str,  # 当前时间
                "chat_history": chat_history,  # 对话历史
                "agent_status": a_des,  # 当前代理状态
                "another_status": o_des,  # 其他代理状态
                "agent": agent.name,  # 当前代理名字
                "another": other.name,  # 其他代理名字
            }
        )

        def _callback(response):
            """解析LLM响应判断是否开始对话
            Args:
                response: LLM的响应文本
            Returns:
                布尔值,True表示开始对话,False表示不开始
            """
            if "No" in response or "no" in response or "否" in response or "不" in response:  # 检查否定词
                return False
            return True  # 没有否定词则返回True

        return {"prompt": prompt, "callback": _callback, "failsafe": False}  # 默认不开始对话

    def prompt_decide_chat_terminate(self, agent, other, chats):
        """决定是否要结束当前对话
        Args:
            agent: 当前代理对象
            other: 其他代理对象
            chats: 当前对话的内容列表
        Returns:
            包含提示、回调函数和默认值的字典
        """
        conversation = "\n".join(["{}: {}".format(n, u) for n, u in chats])  # 将对话内容格式化为字符串
        conversation = (
            conversation or "[对话尚未开始]"  # 如果没有对话内容则使用默认文本
        )

        prompt = self.build_prompt(
            "decide_chat_terminate",  # 使用对话结束决策模板
            {
                "conversation": conversation,  # 对话内容
                "agent": agent.name,  # 当前代理名字
                "another": other.name,  # 其他代理名字
            }
        )

        def _callback(response):
            """解析LLM响应判断是否结束对话
            Args:
                response: LLM的响应文本
            Returns:
                布尔值,True表示结束对话,False表示继续
            """
            if "No" in response or "no" in response or "否" in response or "不" in response:  # 检查否定词
                return False
            return True  # 没有否定词则返回True

        return {"prompt": prompt, "callback": _callback, "failsafe": False}  # 默认不结束对话

    def prompt_decide_wait(self, agent, other, focus):
        """决定是否需要等待其他代理
        Args:
            agent: 当前代理对象
            other: 其他代理对象
            focus: 关注点信息字典
        Returns:
            包含提示、回调函数和默认值的字典
        """
        # 构建第一个示例
        example1 = self.build_prompt(
            "decide_wait_example",  # 使用等待决策示例模板
            {
                "context": "简是丽兹的室友。2022-10-25 07:05，简和丽兹互相问候了早上好。",  # 示例上下文
                "date": "2022-10-25 07:09",  # 示例时间
                "agent": "简",  # 示例代理
                "another": "丽兹",  # 示例其他代理
                "status": "简 正要去浴室",  # 示例代理状态
                "another_status": "丽兹 已经在 使用浴室",  # 示例其他代理状态
                "action": "使用浴室",  # 示例动作
                "another_action": "使用浴室",  # 示例其他代理动作
                "reason": "推理：简和丽兹都想用浴室。简和丽兹同时使用浴室会很奇怪。所以，既然丽兹已经在用浴室了，对简来说最好的选择就是等着用浴室。\n",  # 示例推理过程
                "answer": "答案：<选项A>",  # 示例答案
            }
        )

        # 构建第二个示例
        example2 = self.build_prompt(
            "decide_wait_example",  # 使用等待决策示例模板
            {
                "context": "山姆是莎拉的朋友。2022-10-24 23:00，山姆和莎拉就最喜欢的电影进行了交谈。",  # 示例上下文
                "date": "2022-10-25 12:40",  # 示例时间
                "agent": "山姆",  # 示代理
                "another": "莎拉",  # 示例其他代理
                "status": "山姆 正要去吃午饭",  # 示例代理状态
                "another_status": "莎拉 已经在 洗衣服",  # 示例其他代理状态
                "action": "吃午饭",  # 示例动作
                "another_action": "洗衣服",  # 示例其他代理动作
                "reason": "推理：山姆可能会在餐厅吃午饭。莎拉可能会去洗衣房洗衣服。由于山姆和莎拉需要使用不同的区域，他们的行为并冲突。所以，由于山姆和莎拉将在不同的区域，山姆现在继续吃午饭。\n",  # 示例推理过程
                "answer": "答案：<选项B>",  # 示例答案
            }
        )

        # 构建当前任务的描述
        task = self.build_prompt(
            "decide_wait_example",  # 使用等待决策示例模板
            {
                "context": context,  # 当前上下文
                "date": utils.get_timer().get_date("%Y-%m-%d %H:%M"),  # 当前时间
                "agent": agent.name,  # 当前代理名字
                "another": other.name,  # 其他代理名字
                "status": _status_des(agent),  # 当前代理状态
                "another_status": _status_des(other),  # 其他代理状态
                "action": agent.get_event().get_describe(False),  # 当前代理动作
                "another_action": other.get_event().get_describe(False),  # 其他代理动作
                "reason": "",  # 留空供LLM填写推理过程
                "answer": "",  # 留空供LLM填写答案
            }
        )

        # 构建最终的提示
        prompt = self.build_prompt(
            "decide_wait",  # 使用等待决策模板
            {
                "examples_1": example1,  # 第一个示例
                "examples_2": example2,  # 第二个示例
                "task": task,  # 当前任务
            }
        )

        def _callback(response):
            """解析LLM响应判断是否需要等待
            Args:
                response: LLM的响应文本
            Returns:
                布尔值,True表示需要等待,False表示不需要
            """
            return "A" in response  # 如果响应中包含"A",则需要等待

        return {"prompt": prompt, "callback": _callback, "failsafe": False}  # 默认不等待

    def prompt_generate_chat(self, agent, other, relation, chats):
        """生成对话内容
        Args:
            agent: 当前代理对象
            other: 其他代理对象
            relation: 两代理之间的关系描述
            chats: 当前对话的内容列表
        Returns:
            包含提示、回调函数和默认值的字典
        """
        # 根据关注点和当前事件获取相关记忆
        focus = [relation, other.get_event().get_describe()]  # 关注点列表
        if len(chats) > 4:  # 如果已有超过4条对话
            focus.append("; ".join("{}: {}".format(n, t) for n, t in chats[-4:]))  # 添加最近4条对话
        nodes = agent.associate.retrieve_focus(focus, 15)  # 获取相关记忆节点
        memory = "\n- " + "\n- ".join([n.describe for n in nodes])  # 格式化记忆内容

        # 获取最近的对话记录
        chat_nodes = agent.associate.retrieve_chats(other.name)  # 获取与对方的对话记录
        pass_context = ""  # 初始化历史对话上下文
        for n in chat_nodes:  # 遍历对话记录
            delta = utils.get_timer().get_delta(n.create)  # 计算时间差
            if delta > 480:  # 如果超过480分钟(8小时)
                continue  # 跳过较早的对话
            pass_context += f"{delta} 分钟前，{agent.name} 和 {other.name} 进行过对话。{n.describe}\n"  # 添加对话描述

        address = agent.get_tile().get_address()  # 获取当前位置
        if len(pass_context) > 0:  # 如果有历史对话
            prev_context = f'\n背景：\n"""\n{pass_context}"""\n\n'  # 格式化历史对话上下文
        else:
            prev_context = ""  # 没有历史对话则为空
        # 生成当前状态描述
        curr_context = (
            f"{agent.name} {agent.get_event().get_describe(False)} 时，看到 {other.name} {other.get_event().get_describe(False)}。"
        )

        # 格式化当前对话内容
        conversation = "\n".join(["{}: {}".format(n, u) for n, u in chats])
        conversation = (
            conversation or "[对话尚未开始]"  # 如果没有对话内容则使用默认文本
        )

        prompt = self.build_prompt(
            "generate_chat",  # 使用对话生成模板
            {
                "agent": agent.name,  # 当前代理名字
                "base_desc": self._base_desc(),  # 基础描述
                "memory": memory,  # 相关记忆
                "address": f"{address[-2]}，{address[-1]}",  # 当前位置
                "current_time": utils.get_timer().get_date("%H:%M"),  # 当前时间
                "previous_context": prev_context,  # 历史对话上下文
                "current_context": curr_context,  # 当前状态描述
                "another": other.name,  # 其他代理名字
                "conversation": conversation,  # 当前对话内容
            }
        )

        def _callback(response):
            """解析LLM响应获取对话内容
            Args:
                response: LLM的响应文本
            Returns:
                生成的对话内容
            """
            assert "{" in response and "}" in response  # 确保响应包含JSON格式内容
            json_content = utils.load_dict(
                "{" + response.split("{")[1].split("}")[0] + "}"  # 提取JSON部分
            )
            text = json_content[agent.name].replace("\n\n", "\n").strip(" \n\"'""''")  # 获取并清理对话文本
            return text

        return {
            "prompt": prompt,  # 提示文本
            "callback": _callback,  # 回调函数
            "failsafe": "嗯",  # 默认回复
        }

    def prompt_generate_chat_check_repeat(self, agent, chats, content):
        """检查生成的对话内容是否重复
        Args:
            agent: 当前代理对象
            chats: 当前对话的内容列表
            content: 新生成的对话内容
        Returns:
            包含提示、回调函数和默认值的字典
        """
        # 格式化当前对话内容
        conversation = "\n".join(["{}: {}".format(n, u) for n, u in chats])
        conversation = (
                conversation or "[对话尚未开始]"  # 如果没有对话内容则使用默认文本
        )

        prompt = self.build_prompt(
            "generate_chat_check_repeat",  # 使用对话重复检查模板
            {
                "conversation": conversation,  # 当前对话内容
                "content": f"{agent.name}: {content}",  # 新生成的对话内容
                "agent": agent.name,  # 代理名字
            }
        )

        def _callback(response):
            """解析LLM响应判断对话是否重复
            Args:
                response: LLM的响应文本
            Returns:
                布尔值,True表示重复,False表示不重复
            """
            if "No" in response or "no" in response or "否" in response or "不" in response:  # 检查否定词
                return False
            return True  # 没有否定词则认为重复

        return {"prompt": prompt, "callback": _callback, "failsafe": False}  # 默认认为不重复

    def prompt_summarize_chats(self, chats):
        """生成对话内容的总结
        Args:
            chats: 对话内容列表
        Returns:
            包含提示、回调函数和默认值的字典
        """
        # 格式化对话内容
        conversation = "\n".join(["{}: {}".format(n, u) for n, u in chats])

        prompt = self.build_prompt(
            "summarize_chats",  # 使用对话总结模板
            {
                "conversation": conversation,  # 对话内容
            }
        )

        def _callback(response):
            """解析LLM响应获取对话总结
            Args:
                response: LLM的响应文本
            Returns:
                对话总结文本
            """
            return response.strip()  # 移除首尾空白字符

        # 生成默认的总结文本
        if len(chats) > 1:  # 如果有多轮对话
            failsafe = "{} 和 {} 之间的普通对话".format(chats[0][0], chats[1][0])  # 使用对话双方的名字
        else:  # 如果只有一条消息
            failsafe = "{} 说的话没有得到回应".format(chats[0][0])  # 说明是单向对话

        return {
            "prompt": prompt,  # 提示文本
            "callback": _callback,  # 回调函数
            "failsafe": failsafe,  # 默认总结
        }

    def prompt_reflect_focus(self, nodes, topk):
        """生成关注点的反思问题
        Args:
            nodes: 记忆节点列表
            topk: 需要生成的问题数量
        Returns:
            包含提示、回调函数和默认值的字典
        """
        prompt = self.build_prompt(
            "reflect_focus",  # 使用反思焦点模板
            {
                "reference": "\n".join(["{}. {}".format(idx, n.describe) for idx, n in enumerate(nodes)]),  # 格式化记忆节点列表
                "number": topk,  # 需要生成的问题数量
            }
        )

        def _callback(response):
            """解析LLM响应获取反思问题列表
            Args:
                response: LLM的响应文本
            Returns:
                反思问题列表
            """
            pattern = [
                r"^\d{1}\. (.*)",
                r"^\d{1}\) (.*)",
                r"^\d{1} (.*)"
            ]
            return parse_llm_output(response, pattern, mode="match_all")  # 返回所有匹配的问题

        return {
            "prompt": prompt,  # 提示文本
            "callback": _callback,  # 回调函数
            "failsafe": [  # 默认的反思问题
                "{} 是谁？".format(self.name),
                "{} 住在哪里？".format(self.name),
                "{} 今天要做什么？".format(self.name),
            ],
        }

    def prompt_reflect_insights(self, nodes, topk):
        """从记忆中生成见解
        Args:
            nodes: 记忆节点列表
            topk: 需要生成的见解数量
        Returns:
            包含提示、回调函数和默认值的字典
        """
        prompt = self.build_prompt(
            "reflect_insights",  # 使用反思见解模板
            {
                "reference": "\n".join(["{}. {}".format(idx, n.describe) for idx, n in enumerate(nodes)]),  # 格式化记忆节点列表
                "number": topk,  # 需要生成的见解数量
            }
        )

        def _callback(response):
            """解析LLM响应获取见解列表
            Args:
                response: LLM的响应文本
            Returns:
                见解和相关记忆节点ID的列表
            """
            patterns = [
                r"^\d{1}[\. ]+(.*)[。 ]*[\(（]+.*序号[:： ]+([\d,， ]+)[\)）]",  # 匹配"数字. 见解(序号: x,y)"格式
                r"^\d{1}[\. ]+(.*)[。 ]*[\(（]([\d,， ]+)[\)）]",  # 匹配"数字. 见解(x,y)"格式
            ]
            insights, outputs = [], parse_llm_output(
                response, patterns, mode="match_all"
            )  # 获取所有匹配项
            if outputs:  # 如果找到匹配项
                for output in outputs:
                    if isinstance(output, str):  # 如果只有见解文本
                        insight, node_ids = output, []
                    elif len(output) == 2:  # 如果有见解和节点序号
                        insight, reason = output
                        indices = [int(e.strip()) for e in reason.split(",")]  # 解析节点序号
                        node_ids = [nodes[i].node_id for i in indices if i < len(nodes)]  # 获取对应的节点ID
                    insights.append([insight.strip(), node_ids])  # 添加到见解列表
                return insights
            raise Exception("Can not find insights")  # 如果没有找到见解则抛出异常

        return {
            "prompt": prompt,  # 提示文本
            "callback": _callback,  # 回调函数
            "failsafe": [  # 默认的见解
                [
                    "{} 在考虑下一步该做什么".format(self.name),  # 默认见解文本
                    [nodes[0].node_id],  # 使用第一个节点的ID
                ]
            ],
        }

    def prompt_reflect_chat_planing(self, chats):
        """反思对话内容并生成计划相关的记忆
        Args:
            chats: 对话内容列表
        Returns:
            包含提示、回调函数和默认值的字典
        """
        # 格式化所有对话内容
        all_chats = "\n".join(["{}: {}".format(n, c) for n, c in chats])

        prompt = self.build_prompt(
            "reflect_chat_planing",  # 使用对话计划反思模板
            {
                "conversation": all_chats,  # 对话内容
                "agent": self.name,  # 代理名字
            }
        )

        def _callback(response):
            """解析LLM响应获取反思结果
            Args:
                response: LLM的响应文本
            Returns:
                反思生成的记忆文本
            """
            return response  # 直接返回响应文本

        return {
            "prompt": prompt,  # 提示文本
            "callback": _callback,  # 回调函数
            "failsafe": f"{self.name} 进行了一次对话",  # 默认记忆文本
        }

    def prompt_reflect_chat_memory(self, chats):
        """反思对话内容并生成一般记忆
        Args:
            chats: 对话内容列表
        Returns:
            包含提示、回调函数和默认值的字典
        """
        # 格式化所有对话内容
        all_chats = "\n".join(["{}: {}".format(n, c) for n, c in chats])

        prompt = self.build_prompt(
            "reflect_chat_memory",  # 使用对话记忆反思模板
            {
                "conversation": all_chats,  # 对话内容
                "agent": self.name,  # 代理名字
            }
        )

        def _callback(response):
            """解析LLM响应获取反思结果
            Args:
                response: LLM的响应文本
            Returns:
                反思生成的记忆文本
            """
            return response  # 直接返回响应文本

        return {
            "prompt": prompt,  # 提示文本
            "callback": _callback,  # 回调函数
            "failsafe": f"{self.name} 进行了一次对话",  # 默认记忆文本
        }

    def prompt_retrieve_plan(self, nodes):
        """从记忆中检索相关计划
        Args:
            nodes: 记忆节点列表
        Returns:
            包含提示、回调函数和默认值的字典
        """
        # 格式化记忆节点为时间戳+描述的格式
        statements = [
            n.create.strftime("%Y-%m-%d %H:%M") + ": " + n.describe for n in nodes
        ]

        prompt = self.build_prompt(
            "retrieve_plan",  # 使用计划检索模板
            {
                "description": "\n".join(statements),  # 记忆描述列表
                "agent": self.name,  # 代理名字
                "date": utils.get_timer().get_date("%Y-%m-%d"),  # 当前日期
            }
        )

        def _callback(response):
            """解析LLM响应获取计划列表
            Args:
                response: LLM的响应文本
            Returns:
                计划描述列表
            """
            pattern = [
                r"^\d{1,2}\. (.*)。",  # 匹配"数字. 内容。"格式
                r"^\d{1,2}\. (.*)",  # 匹配"数字. 内容"格式
                r"^\d{1,2}\) (.*)。",  # 匹配"数字) 内容。"格式
                r"^\d{1,2}\) (.*)",  # 匹配"数字) 内容"格式
            ]
            return parse_llm_output(response, pattern, mode="match_all")  # 返回所有匹配的计划

        return {
            "prompt": prompt,  # 提示文本
            "callback": _callback,  # 回调函数
            "failsafe": [r.describe for r in random.choices(nodes, k=5)],  # 默认随机选择5个记忆作为计划
        }

    def prompt_retrieve_thought(self, nodes):
        """从记忆中检索相关想法
        Args:
            nodes: 记忆节点列表
        Returns:
            包含提示、回调函数和默认值的字典
        """
        # 格式化记忆节点为时间戳+描述的格式
        statements = [
            n.create.strftime("%Y-%m-%d %H:%M") + "：" + n.describe for n in nodes
        ]

        prompt = self.build_prompt(
            "retrieve_thought",  # 使用想法检索模板
            {
                "description": "\n".join(statements),  # 记忆描述列表
                "agent": self.name,  # 代理名字
            }
        )

        def _callback(response):
            """解析LLM响应获取想法文本
            Args:
                response: LLM的响应文本
            Returns:
                想法描述文本
            """
            return response  # 直接返回响应文本

        return {
            "prompt": prompt,  # 提示文本
            "callback": _callback,  # 回调函数
            "failsafe": "{} 应该遵循昨天的日程".format(self.name),  # 默认想法
        }

    def prompt_retrieve_currently(self, plan_note, thought_note):
        """从记忆中检索并生成当前状态描述
        Args:
            plan_note: 计划相关的记忆列表
            thought_note: 想法相关的记忆文本
        Returns:
            包含提示、回调函数和默认值的字典
        """
        # 获取昨天的日期时间戳
        time_stamp = (
            utils.get_timer().get_date() - datetime.timedelta(days=1)
        ).strftime("%Y-%m-%d")

        prompt = self.build_prompt(
            "retrieve_currently",  # 使用当前状态检索模板
            {
                "agent": self.name,  # 代理名字
                "time": time_stamp,  # 昨天的日期
                "currently": self.currently,  # 当前状态
                "plan": ". ".join(plan_note),  # 计划记忆
                "thought": thought_note,  # 想法记忆
                "current_time": utils.get_timer().get_date("%Y-%m-%d"),  # 当前日期
            }
        )

        def _callback(response):
            """解析LLM响应获取当前状态描述
            Args:
                response: LLM的响应文本
            Returns:
                当前状态描述文本
            """
            pattern = [
                r"^状态: (.*)。",  # 匹配"状态: xxx。"格式
                r"^状态: (.*)",  # 匹配"状态: xxx"格式
            ]
            return parse_llm_output(response, pattern)  # 返回解析出的状态描述

        return {
            "prompt": prompt,  # 提示文本
            "callback": _callback,  # 回调函数
            "failsafe": self.currently,  # 默认返回当前状态
        }

    def prompt_summarize_relation(self, agent, other_name):
        """生成代理间关系的总结
        Args:
            agent: 当前代理对象
            other_name: 其他代理的名字
        Returns:
            包含提示、回调函数和默认值的字典
        """
        # 获取与另一个代理相关的记忆
        nodes = agent.associate.retrieve_focus([other_name], 50)

        prompt = self.build_prompt(
            "summarize_relation",  # 使用关系总结模板
            {
                "context": "\n".join(["{}. {}".format(idx, n.describe) for idx, n in enumerate(nodes)]),
                "agent": agent.name,  # 当前代理名字
                "another": other_name,  # 其他代理名字
            }
        )

        def _callback(response):
            """解析LLM响应获取关系描述
            Args:
                response: LLM的响应文本
            Returns:
                关系描述文本
            """
            return response

        return {
            "prompt": prompt,  # 提示文本
            "callback": _callback,  # 回调函数
            "failsafe": agent.name + " 认识 " + other_name,  # 默认关系描述
        }

    def prompt_generate_painting_prompt(self, agent):
        """生成绘画提示词
        Args:
            agent: 智能体对象
        Returns:
            包含提示、回调函数和默认值的字典
        """
        # 获取最近的记忆
        memory_nodes = agent.associate.retrieve_events() + agent.associate.retrieve_thoughts()
        memory_str = "\\n".join([f"{node.create.strftime('%Y-%m-%d %H:%M')}：{node.describe}" for node in memory_nodes])

        prompt_data = {
            "agent": self.name, 
            "memory": memory_str,
            "innate": self.config.get("innate", "未知"),
            "learned": self.config.get("learned", "未知"),
            "lifestyle": self.config.get("lifestyle", "未知")
        }

        prompt = self.build_prompt(
            "generate_painting_prompt",
            prompt_data
        )

        def _callback(response):
            """解析LLM响应获取绘画内容
            Args:
                response: LLM的响应文本
            Returns:
                绘画内容描述文本
            """
            return response

        return {
            "prompt": prompt,
            "callback": _callback,
            "failsafe": f"{agent.name} 正在思考要画什么",
        }

    def prompt_generate_music_prompt(self, agent):
        """生成音乐创作提示词
        Args:
            agent: 智能体对象
        Returns:
            包含提示、回调函数和默认值的字典
        """
        # 获取最近的记忆
        memory_nodes = agent.associate.retrieve_events() + agent.associate.retrieve_thoughts()
        memory = "\n".join([f"{node.create.strftime('%Y-%m-%d %H:%M')}：{node.describe}" for node in memory_nodes])

        prompt_data = {
                "agent": agent.name,
                "base_desc": self._base_desc(), # 添加基础描述以保持一致性
                "memory": memory,
            "innate": self.config.get("innate", "未知"),
            "learned": self.config.get("learned", "未知"),
            "lifestyle": self.config.get("lifestyle", "未知")
            }

        prompt = self.build_prompt(
            "generate_music_prompt",
            prompt_data
        )

        def _callback(response):
            """解析LLM响应获取音乐内容
            Args:
                response: LLM的响应文本
            Returns:
                音乐内容描述文本
            """
            return response

        return {
            "prompt": prompt,
            "callback": _callback,
            "failsafe": f"{agent.name} 正在构思一段旋律",
        }

    def prompt_generate_game_life_rule(self, agent):
        """生成生命游戏规则提示词
        Args:
            agent: 智能体对象
        Returns:
            包含提示、回调函数和默认值的字典
        """
        # 获取最近的记忆
        # agent here is the Agent instance passed from agent.py
        memory_nodes = agent.associate.retrieve_events() + agent.associate.retrieve_thoughts()
        # 按创建时间排序，最新的在前，并限制数量以避免提示过长
        memory_nodes.sort(key=lambda x: x.create, reverse=True)
        memory_nodes = memory_nodes[:20] # 例如，最多取最近的20条记忆

        memory_str = "\\n".join([f"{node.create.strftime('%Y-%m-%d %H:%M')}：{node.describe}" for node in memory_nodes])
        if not memory_str:
            memory_str = "无特定记忆片段可参考。"

        # self.name 是 Scratch 实例的 name, 在 Agent 初始化 Scratch 时被设为 agent.name
        # self.config 是 Agent 实例的主配置字典，在 Agent 初始化 Scratch 时传入
        prompt_data = {
            "agent": self.name, 
            "memory": memory_str,
            "innate": self.config.get("innate", "未知"),
            "learned": self.config.get("learned", "未知"),
            "lifestyle": self.config.get("lifestyle", "未知")
        }

        prompt = self.build_prompt(
            "generate_game_life_rule", # 这会加载 data/prompts/generate_game_life_rule.txt
            prompt_data
        )

        def _callback(response):
            """解析LLM响应获取生命游戏规则描述
            Args:
                response: LLM的响应文本
            Returns:
                生命游戏规则描述文本
            """
            return response.strip() # 简单的回调，直接返回去除首尾空格的响应

        return {
            "prompt": prompt,
            "callback": _callback,
            "failsafe": f"{self.name} 正在思考一个全新的生命游戏规则。", # LLM调用失败时的备用回复
        }

    def prompt_chat_summary(self, agent_name, other_name, now_summary, events):
        """生成对话内容的总结
        Args:
            agent_name: 当前代理的名字
            other_name: 其他代理的名字
            now_summary: 当前对话内容的总结
            events: 对话内容列表
        Returns:
            包含提示、回调函数和默认值的字典
        """
        prompt = self.build_prompt(
            "chat_summary",  # 使用对话总结模板
            {
                "agent_name": agent_name,  # 当前代理名字
                "other_name": other_name,  # 其他代理名字
                "now_summary": now_summary,  # 当前对话内容的总结
                "events": ", ".join(events),  # 对话内容列表
            }
        )

        def _callback(response):
            """解析LLM响应获取对话总结
            Args:
                response: LLM的响应文本
            Returns:
                对话总结文本
            """
            return response.strip()  # 移除首尾空白字符

        # 生成默认的总结文本
        if len(events) > 1:  # 如果有多轮对话
            failsafe = "{} 和 {} 之间的普通对话".format(events[0], events[1])  # 使用对话双方的名字
        else:  # 如果只有一条消息
            failsafe = "{} 说的话没有得到回应".format(events[0])  # 说明是单向对话

        return {
            "prompt": prompt,  # 提示文本
            "callback": _callback,  # 回调函数
            "failsafe": failsafe,  # 默认总结
        }
