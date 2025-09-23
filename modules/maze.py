"""
这个模块实现了一个迷宫系统,包含两个主要类:
1. Tile类 - 表示迷宫中的一个格子单元,存储格子的位置、属性和事件等信息
2. Maze类 - 表示整个迷宫地图,管理所有格子并提供寻路等功能
"""

import random  # 导入随机数模块,用于随机选择位置等功能
from itertools import product  # 导入product函数,用于生成坐标组合

from modules import utils  # 导入工具函数
from modules.memory.event import Event  # 导入事件类,用于处理格子中的事件


class Tile:
    """
    Tile类表示迷宫中的一个格子单元
    """
    def __init__(
        self,
        coord,  # 格子的坐标 (x,y)
        world,  # 所属的世界名称
        address_keys,  # 地址键列表,用于定位格子
        address=None,  # 完整地址列表
        collision=False,  # 是否为障碍物
    ):
        # 初始化一个格子的基本属性
        self.coord = coord  # 存储格子坐标
        self.address = [world]  # 地址列表,首先包含世界名称
        if address:  # 如果提供了额外的地址信息
            self.address += address  # 添加到地址列表中
        self.address_keys = address_keys  # 存储地址键列表
        # 创建地址映射字典,将地址键和实际地址值对应
        self.address_map = dict(zip(address_keys[: len(self.address)], self.address))
        self.collision = collision  # 设置是否为障碍物
        self.event_cnt = 0  # 事件计数器
        self._events = {}  # 存储格子上的事件的字典
        # 如果地址长度为4(完整地址),则添加一个新事件
        if len(self.address) == 4:
            self.add_event(Event(self.address[-1], address=self.address))

    def abstract(self):
        """返回格子的摘要信息,包括坐标和事件"""
        address = ":".join(self.address)  # 将地址列表转换为字符串
        if self.collision:
            address += "(collision)"  # 如果是障碍物,添加标记
        return {
            "coord[{},{}]".format(self.coord[0], self.coord[1]): address,  # 返回坐标和地址
            "events": {k: str(v) for k, v in self.events.items()},  # 返回所有事件的字符串表示
        }

    def __str__(self):
        """将格子信息转换为字符串"""
        return utils.dump_dict(self.abstract())  # 使用工具函数转换字典为字符串

    def __eq__(self, other):
        """比较两个格子是否相等(基于坐标)"""
        if isinstance(other, Tile):  # 如果比较对象也是Tile类
            return hash(self.coord) == hash(other.coord)  # 比较坐标的哈希值
        return False

    def get_events(self):
        """获取格子上的所有事件"""
        return self.events.values()  # 返回事件字典中的所有事件对象

    def add_event(self, event):
        """向格子添加新事件"""
        if isinstance(event, (tuple, list)):  # 如果事件是元组或列表形式
            event = Event.from_list(event)  # 将其转换为Event对象
        # 检查是否已存在相同事件,如果都不相同则添加
        if all(e != event for e in self._events.values()):
            self._events["e_" + str(self.event_cnt)] = event  # 添加新事件,使用计数器作为键
            self.event_cnt += 1  # 事件计数器加1
        return event  # 返回添加的事件

    def remove_events(self, subject=None, event=None):
        """移除格子上的指定事件
        subject: 事件主体
        event: 具体事件对象
        """
        r_events = {}  # 存储要移除的事件
        for tag, eve in self._events.items():
            if subject and eve.subject == subject:  # 如果指定了主体且匹配
                r_events[tag] = eve
            if event and eve == event:  # 如果指定了事件且匹配
                r_events[tag] = eve
        # 从事件字典中移除匹配的事件
        for r_eve in r_events:
            self._events.pop(r_eve)
        return r_events  # 返回被移除的事件

    def update_events(self, event, match="subject"):
        """更新格子上的事件
        event: 新的事件对象
        match: 匹配方式,默认按主体匹配
        """
        u_events = {}  # 存储更新的事件
        for tag, eve in self._events.items():
            if match == "subject" and eve.subject == event.subject:  # 如果主体匹配
                self._events[tag] = event  # 用新事件替换旧事件
                u_events[tag] = event
        return u_events  # 返回更新的事件

    def has_address(self, key):
        """检查是否包含指定的地址键"""
        return key in self.address_map

    def get_address(self, level=None, as_list=True):
        """获取指定层级的地址
        level: 地址层级
        as_list: 是否返回列表形式
        """
        level = level or self.address_keys[-1]  # 如果未指定层级,使用最后一个层级
        # 确保指定的层级存在
        assert level in self.address_keys, "Can not find {} from {}".format(
            level, self.address_keys
        )
        pos = self.address_keys.index(level) + 1  # 获取层级位置
        if as_list:
            return self.address[:pos]  # 返回列表形式的地址
        return ":".join(self.address[:pos])  # 返回字符串形式的地址

    def get_addresses(self):
        """获取所有可能的地址组合
        返回从第二级开始到当前层级的所有地址组合"""
        addresses = []
        if len(self.address) > 1:  # 如果地址长度大于1(不只包含world)
            # 生成从2到当前地址长度的所有地址组合
            addresses = [
                ":".join(self.address[:i]) for i in range(2, len(self.address) + 1)
            ]
        return addresses

    @property
    def events(self):
        """事件属性的getter方法,返回所有事件"""
        return self._events

    @property
    def is_empty(self):
        """检查格子是否为空
        当格子只有world地址且没有事件时为空"""
        return len(self.address) == 1 and not self._events


class Maze:
    """迷宫类,管理整个迷宫地图系统"""
    def __init__(self, config, logger):
        """初始化迷宫
        config: 配置信息字典
        logger: 日志记录器
        """
        # 定义迷宫的基本属性
        self.maze_height, self.maze_width = config["size"]  # 迷宫的高度和宽度
        self.tile_size = config["tile_size"]  # 每个格子的大小
        address_keys = config["tile_address_keys"]  # 地址键列表
        
        # 创建迷宫网格,初始化每个位置的Tile对象
        self.tiles = [
            [
                Tile((x, y), config["world"], address_keys)
                for x in range(self.maze_width)
            ]
            for y in range(self.maze_height)
        ]
        
        # 根据配置更新特定位置的格子属性
        for tile in config["tiles"]:
            x, y = tile.pop("coord")  # 获取并移除坐标信息
            self.tiles[y][x] = Tile((x, y), config["world"], address_keys, **tile)

        # 初始化地址到格子坐标的映射字典
        self.address_tiles = dict()
        for i in range(self.maze_height):
            for j in range(self.maze_width):
                # 获取每个格子的所有可能地址,并建立映射关系
                for add in self.tile_at([j, i]).get_addresses():
                    self.address_tiles.setdefault(add, set()).add((j, i))

        self.logger = logger  # 保存日志记录器

    def find_path(self, src_coord, dst_coord):
        """使用广度优先搜索(BFS)算法寻找从起点到终点的路径
        src_coord: 起点坐标
        dst_coord: 终点坐标
        返回: 路径坐标列表
        """
        # 创建一个与迷宫同样大小的二维数组,用于记录到达每个位置的步数
        map = [[0 for _ in range(self.maze_width)] for _ in range(self.maze_height)]
        frontier = [src_coord]  # 初始化前沿队列,包含起点
        visited = set()  # 记录已访问的位置
        map[src_coord[1]][src_coord[0]] = 1  # 标记起点步数为1

        # 当还没有到达终点时,继续搜索
        while map[dst_coord[1]][dst_coord[0]] == 0:
            new_frontier = []  # 存储下一轮要访问的位置
            for f in frontier:  # 遍历当前前沿的所有位置
                # 获取当前位置周围的可行位置
                for c in self.get_around(f):
                    # 检查位置是否在有效范围内且未访问过
                    if (
                        0 < c[0] < self.maze_width - 1
                        and 0 < c[1] < self.maze_height - 1
                        and map[c[1]][c[0]] == 0
                        and c not in visited
                    ):
                        # 记录到达该位置的步数(当前位置步数+1)
                        map[c[1]][c[0]] = map[f[1]][f[0]] + 1
                        new_frontier.append(c)  # 添加到下一轮要访问的位置
                        visited.add(c)  # 标记为已访问
            frontier = new_frontier  # 更新前沿队列

        # 从终点回溯到起点,构建路径
        step = map[dst_coord[1]][dst_coord[0]]  # 获取到达终点的步数
        path = [dst_coord]  # 路径列表,从终点开始
        # 从终点往回找,直到回到起点
        while step > 1:
            # 检查当前位置周围的点
            for c in self.get_around(path[-1]):
                # 如果找到前一步的位置
                if map[c[1]][c[0]] == step - 1:
                    path.append(c)  # 添加到路径中
                    break
            step -= 1  # 步数减1
        return path[::-1]  # 返回反转后的路径(从起点到终点)

    def tile_at(self, coord):
        """获取指定坐标的格子对象
        coord: 坐标元组(x,y)"""
        return self.tiles[coord[1]][coord[0]]  # 返回对应位置的Tile对象

    def update_obj(self, coord, obj_event):
        """更新指定坐标的对象事件
        coord: 坐标元组(x,y)
        obj_event: 要更新的对象事件
        """
        tile = self.tile_at(coord)  # 获取指定坐标的格子
        # 如果格子没有game_object层级的地址,直接返回
        if not tile.has_address("game_object"):
            return
        # 如果事件的地址与格子的地址不匹配,直接返回
        if obj_event.address != tile.get_address("game_object"):
            return
        # 将事件地址转换为字符串形式
        addr = ":".join(obj_event.address)
        # 如果地址不在映射字典中,直接返回
        if addr not in self.address_tiles:
            return
        # 更新所有具有相同地址的格子的事件
        for c in self.address_tiles[addr]:
            self.tile_at(c).update_events(obj_event)

    def get_scope(self, coord, config):
        """获取指定坐标周围的视野范围内的所有格子
        coord: 中心坐标
        config: 视野配置,包含视野半径和模式
        返回: 视野范围内的格子列表
        """
        coords = []  # 存储视野范围内的坐标
        vision_r = config["vision_r"]  # 视野半径
        if config["mode"] == "box":  # 如果是矩形视野模式
            # 计算视野范围的x坐标范围
            x_range = [
                max(coord[0] - vision_r, 0),  # 左边界不小于0
                min(coord[0] + vision_r + 1, self.maze_width),  # 右边界不超过迷宫宽度
            ]
            # 计算视野范围的y坐标范围
            y_range = [
                max(coord[1] - vision_r, 0),  # 上边界不小于0
                min(coord[1] + vision_r + 1, self.maze_height),  # 下边界不超过迷宫高度
            ]
            # 生成视野范围内的所有坐标组合
            coords = list(product(list(range(*x_range)), list(range(*y_range))))
        return [self.tile_at(c) for c in coords]  # 返回所有坐标对应的格子对象

    def get_around(self, coord, no_collision=True):
        """获取指定坐标周围的相邻格子坐标
        coord: 中心坐标
        no_collision: 是否排除障碍物格子
        返回: 相邻格子的坐标列表
        """
        # 获取上下左右四个相邻位置的坐标
        coords = [
            (coord[0] - 1, coord[1]),  # 左
            (coord[0] + 1, coord[1]),  # 右
            (coord[0], coord[1] - 1),  # 上
            (coord[0], coord[1] + 1),  # 下
        ]
        # 如果需要排除障碍物,则过滤掉collision为True的格子
        if no_collision:
            coords = [c for c in coords if not self.tile_at(c).collision]
        return coords

    def get_address_tiles(self, address):
        """获取具有指定地址的所有格子坐标
        address: 地址列表
        返回: 格子坐标集合或随机一个地址的格子坐标集合
        """
        addr = ":".join(address)  # 将地址列表转换为字符串
        # 如果地址存在于映射中,返回对应的坐标集合
        if addr in self.address_tiles:
            return self.address_tiles[addr]
        
        # 否则（如果特定地址找不到），从所有已知的地址的坐标集合中随机选择一个返回
        # 这模仿了参考代码的行为，但在选择前确保列表不为空
        all_tile_collections = list(self.address_tiles.values())
        if not all_tile_collections:
            # 如果没有任何地址的坐标集合（非常罕见的情况，除非 self.address_tiles 为空）
            self.logger.warning(f"Maze.get_address_tiles: No specific address '{addr}' found and no other addresses available to choose from.")
            return set()  # 返回一个空集合，因为期望的是一个坐标集合
        
        # 从所有地址的坐标集合中随机选择一个集合返回
        return random.choice(all_tile_collections)
