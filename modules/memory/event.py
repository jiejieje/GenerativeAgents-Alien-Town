"""
这个模块实现了事件系统:
Event类表示一个具体事件,包含主谓宾结构和位置信息
"""


class Event:
    """事件类,表示一个具体的事件或状态"""
    
    def __init__(
        self,
        subject,  # 事件主体
        predicate=None,  # 谓语
        object=None,  # 宾语
        address=None,  # 地址列表
        describe=None,  # 事件描述
        emoji=None,  # 表情符号
    ):
        """初始化一个事件
        subject: 事件的主体(通常是代理人名称)
        predicate: 谓语(动作),默认为"此时"
        object: 宾语(动作对象),默认为"空闲"
        address: 事件发生的位置,以列表形式存储
        describe: 事件的文字描述
        emoji: 相关的表情符号
        """
        self.subject = subject  # 保存主体
        self.predicate = predicate or "此时"  # 设置谓语,默认"此时"
        self.object = object or "空闲"  # 设置宾语,默认"空闲"
        self._describe = describe or ""  # 保存描述文本
        self.address = address or []  # 保存地址列表
        self.emoji = emoji or ""  # 保存表情符号

    def __str__(self):
        """将事件转换为字符串形式"""
        if self._describe:  # 如果有描述文本
            des = "{}".format(self._describe)  # 直接使用描述
        else:
            # 否则使用主谓宾结构
            des = "{} {} {}".format(self.subject, self.predicate, self.object)
            
        # 如果有地址信息,添加到描述后面
        if self.address:
            des += " @ " + ":".join(self.address)
        return des

    def __hash__(self):
        """计算事件的哈希值(用于比较和去重)"""
        return hash(
            (
                self.subject,  # 主体
                self.predicate,  # 谓语
                self.object,  # 宾语
                self._describe,  # 描述
                ":".join(self.address),  # 地址字符串
            )
        )

    def __eq__(self, other):
        """比较两个事件是否相等
        other: 另一个事件对象
        返回: 布尔值,表示是否相等
        """
        if isinstance(other, Event):  # 如果是Event类型
            return hash(self) == hash(other)  # 比较哈希值
        return False  # 其他类型都不相等

    def update(self, predicate=None, object=None, describe=None):
        """更新事件的属性
        predicate: 新的谓语
        object: 新的宾语
        describe: 新的描述文本
        """
        self.predicate = predicate or "此时"  # 更新谓语
        self.object = object or "空闲"  # 更新宾语
        self._describe = describe or self._describe  # 更新描述

    def to_id(self):
        """获取事件的唯一标识元组
        返回: (主体,谓语,宾语,描述)的元组
        """
        return self.subject, self.predicate, self.object, self._describe

    def fit(self, subject=None, predicate=None, object=None):
        """检查事件是否匹配指定的主谓宾
        subject/predicate/object: 要匹配的主谓宾(None表示不检查)
        返回: 布尔值,表示是否匹配
        """
        if subject and self.subject != subject:  # 检查主体
            return False
        if predicate and self.predicate != predicate:  # 检查谓语
            return False
        if object and self.object != object:  # 检查宾语
            return False
        return True  # 所有检查都通过

    def to_dict(self):
        """将事件转换为字典形式(用于序列化)
        返回: 包含事件所有属性的字典
        """
        return {
            "subject": self.subject,  # 主体
            "predicate": self.predicate,  # 谓语
            "object": self.object,  # 宾语
            "describe": self._describe,  # 描述
            "address": self.address,  # 地址
            "emoji": self.emoji,  # 表情
        }

    def get_describe(self, with_subject=True):
        """获取事件的描述文本
        with_subject: 是否包含主体
        返回: 格式化的描述文本
        """
        # 使用描述文本或谓语+宾语的组合
        describe = self._describe or "{} {}".format(self.predicate, self.object)
        subject = ""
        if with_subject:  # 如果需要包含主体
            if self.subject not in describe:  # 且描述中没有主体
                subject = self.subject + " "  # 添加主体
        else:  # 如果不需要主体
            if describe.startswith(self.subject + " "):  # 但描述以主体开头
                describe = describe[len(self.subject) + 1:]  # 移除主体
        return "{}{}".format(subject, describe)  # 返回最终描述

    @classmethod
    def from_dict(cls, config):
        """从字典创建事件对象(用于反序列化)
        config: 配置字典
        返回: 新的Event实例
        """
        return cls(**config)

    @classmethod
    def from_list(cls, event):
        """从列表创建事件对象
        event: 事件列表(包含主谓宾和可选的地址)
        返回: 新的Event实例
        """
        if len(event) == 3:  # 如果只有主谓宾
            return cls(event[0], event[1], event[2])
        # 如果还包含地址
        return cls(event[0], event[1], event[2], event[3])
