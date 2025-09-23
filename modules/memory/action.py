"""
这个模块实现了代理人的行动系统:
1. Action类 - 表示一个具体的行动,包含事件、时间和状态信息
2. 提供行动的序列化和反序列化功能
"""

import datetime  # 导入日期时间处理模块

from modules import utils  # 导入工具函数
from .event import Event  # 导入事件类


class Action:
    """行动类,表示代理人的一个具体行动"""
    
    def __init__(
        self,
        event,  # 主要事件对象
        obj_event=None,  # 相关的对象事件(可选)
        start=None,  # 开始时间
        duration=0,  # 持续时间(分钟)
    ):
        """初始化一个行动
        event: 主要事件对象
        obj_event: 相关的对象事件(比如交互对象)
        start: 开始时间,如果不指定则使用当前时间
        duration: 持续时间(分钟)
        """
        self.event = event  # 保存主要事件
        self.obj_event = obj_event  # 保存对象事件
        self.start = start or utils.get_timer().get_date()  # 设置开始时间
        self.duration = duration  # 保存持续时间
        # 计算结束时间(开始时间加上持续时间)
        self.end = self.start + datetime.timedelta(minutes=self.duration)

    def abstract(self):
        """生成行动的摘要信息
        返回: 包含状态和事件信息的字典
        """
        # 生成状态描述(包含完成状态和时间范围)
        status = "{} [{}~{}]".format(
            "已完成" if self.finished() else "进行中",
            self.start.strftime("%Y%m%d-%H:%M"),
            self.end.strftime("%Y%m%d-%H:%M"),
        )
        # 创建信息字典
        info = {"status": status, "event": str(self.event)}
        # 如果有对象事件,添加到信息中
        if self.obj_event:
            info["object"] = str(self.obj_event)
        return info

    def __str__(self):
        """将行动转换为字符串形式"""
        return utils.dump_dict(self.abstract())  # 使用工具函数转换字典为字符串

    def finished(self):
        """检查行动是否已完成
        返回: 布尔值,表示是否完成
        """
        if not self.duration:  # 如果没有持续时间,视为已完成
            return True
        if not self.event.address:  # 如果事件没有地址,视为已完成
            return True
        # 检查当前时间是否超过结束时间
        return utils.get_timer().get_date() > self.end

    def to_dict(self):
        """将行动转换为字典形式(用于序列化)
        返回: 包含行动信息的字典
        """
        return {
            "event": self.event.to_dict(),  # 转换主事件
            "obj_event": self.obj_event.to_dict() if self.obj_event else None,  # 转换对象事件(如果有)
            "start": self.start.strftime("%Y%m%d-%H:%M:%S"),  # 格式化开始时间
            "duration": self.duration,  # 保存持续时间
        }

    @classmethod
    def from_dict(cls, config):
        """从字典创建行动对象(用于反序列化)
        config: 配置字典
        返回: 新的Action实例
        """
        config["event"] = Event.from_dict(config["event"])  # 转换主事件
        if config.get("obj_event"):  # 如果有对象事件
            config["obj_event"] = Event.from_dict(config["obj_event"])  # 转换对象事件
        config["start"] = utils.to_date(config["start"])  # 解析开始时间
        return cls(**config)  # 创建新的Action实例
