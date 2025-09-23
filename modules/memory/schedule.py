"""
这个模块实现了代理人的日程安排系统:
Schedule类管理代理人的每日计划和活动分解
"""

from modules import utils  # 导入工具函数


class Schedule:
    """日程安排类,管理代理人的活动计划"""
    
    def __init__(self, create=None, daily_schedule=None, diversity=5, max_try=5):
        """初始化日程安排
        create: 创建时间
        daily_schedule: 初始日程列表
        diversity: 活动多样性参数
        max_try: 最大尝试次数
        """
        # 设置创建时间
        if create:
            self.create = utils.to_date(create)  # 解析时间字符串
        else:
            self.create = None  # 无创建时间
            
        self.daily_schedule = daily_schedule or []  # 初始化日程列表
        self.diversity = diversity  # 活动多样性参数
        self.max_try = max_try  # 最大尝试次数

    def abstract(self):
        """生成日程的摘要信息
        返回: 包含时间段和活动描述的字典
        """
        def _to_stamp(plan):
            """将计划转换为时间戳字符串"""
            start, end = self.plan_stamps(plan, time_format="%H:%M")
            return "{}~{}".format(start, end)

        des = {}  # 存储描述信息
        for plan in self.daily_schedule:  # 遍历所有计划
            stamp = _to_stamp(plan)  # 获取时间戳
            if plan.get("decompose"):  # 如果有子计划
                # 创建子计划的时间-描述映射
                s_info = {_to_stamp(p): p["describe"] for p in plan["decompose"]}
                des[stamp + ": " + plan["describe"]] = s_info  # 添加主计划和子计划
            else:
                des[stamp] = plan["describe"]  # 只添加主计划
        return des

    def __str__(self):
        """将日程转换为字符串形式"""
        return utils.dump_dict(self.abstract())

    def add_plan(self, describe, duration, decompose=None):
        """添加新的计划
        describe: 计划描述
        duration: 持续时间(分钟)
        decompose: 子计划列表
        返回: 添加的计划字典
        """
        # 如果已有计划,从最后一个计划的结束时间开始
        if self.daily_schedule:
            last_plan = self.daily_schedule[-1]
            start = last_plan["start"] + last_plan["duration"]
        else:
            start = 0  # 否则从0开始
            
        # 添加新计划到日程列表
        self.daily_schedule.append(
            {
                "idx": len(self.daily_schedule),  # 计划索引
                "describe": describe,  # 计划描述
                "start": start,  # 开始时间
                "duration": duration,  # 持续时间
                "decompose": decompose or {},  # 子计划(如果有)
            }
        )
        return self.daily_schedule[-1]  # 返回添加的计划

    def current_plan(self):
        """获取当前正在执行的计划
        返回: (主计划,当前执行的子计划或主计划本身)的元组
        """
        # 获取当前时间(分钟数)
        total_minute = utils.get_timer().daily_duration()
        
        # 遍历所有计划
        for plan in self.daily_schedule:
            # 跳过已结束的计划
            if self.plan_stamps(plan)[1] <= total_minute:
                continue
            # 检查子计划
            for de_plan in plan.get("decompose", []):
                # 跳过已结束的子计划
                if self.plan_stamps(de_plan)[1] <= total_minute:
                    continue
                return plan, de_plan  # 返回主计划和当前子计划
            return plan, plan  # 如果没有子计划,返回主计划两次
            
        # 如果所有计划都结束,返回最后一个计划
        last_plan = self.daily_schedule[-1]
        return last_plan, last_plan

    def plan_stamps(self, plan, time_format=None):
        """获取计划的开始和结束时间
        plan: 计划字典
        time_format: 时间格式字符串(可选)
        返回: (开始时间,结束时间)元组
        """
        def _to_date(minutes):
            """将分钟数转换为时间字符串"""
            return utils.get_timer().daily_time(minutes).strftime(time_format)

        # 计算开始和结束时间(分钟数)
        start, end = plan["start"], plan["start"] + plan["duration"]
        # 如果指定了格式,转换为时间字符串
        if time_format:
            start, end = _to_date(start), _to_date(end)
        return start, end

    def decompose(self, plan):
        """检查计划是否需要分解为子计划
        plan: 计划字典
        返回: 布尔值,表示是否需要分解
        """
        # 如果已有子计划,不需要再分解
        d_plan = plan.get("decompose", {})
        if len(d_plan) > 0:
            return False
            
        describe = plan["describe"]  # 获取计划描述
        
        # 检查是否包含睡眠相关词汇
        if "sleep" not in describe and "bed" not in describe:
            return True
        if "睡" not in describe and "床" not in describe:
            return True
            
        # 检查是否是正在睡眠的状态
        if "sleeping" in describe or "asleep" in describe or "in bed" in describe:
            return False
        if "睡" in describe or "床" in describe:
            return False
            
        # 对于短时间的睡眠相关活动,允许分解
        if "sleep" in describe or "bed" in describe:
            return plan["duration"] <= 60
        if "睡" in describe or "床" in describe:
            return plan["duration"] <= 60
            
        return True  # 其他情况都允许分解

    def scheduled(self):
        """检查当前日程是否是今天的
        返回: 布尔值,表示是否是今天的日程
        """
        if not self.daily_schedule:  # 如果没有日程
            return False
        # 比较创建日期和当前日期
        return utils.get_timer().daily_format() == self.create.strftime("%A %B %d")

    def to_dict(self):
        """将日程转换为字典形式(用于序列化)
        返回: 包含日程信息的字典
        """
        return {
            "create": (
                self.create.strftime("%Y%m%d-%H:%M:%S") if self.create else None
            ),  # 创建时间
            "daily_schedule": self.daily_schedule,  # 日程列表
        }
