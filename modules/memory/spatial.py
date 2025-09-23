"""
这个模块实现了代理人的空间认知系统:
Spatial类管理代理人对空间位置的理解和导航
"""

import random  # 导入随机数模块

from modules import utils  # 导入工具函数


class Spatial:
    """空间认知类,管理位置信息和空间导航"""
    
    def __init__(self, tree, address=None):
        """初始化空间认知系统
        tree: 空间结构树
        address: 地址映射字典
        """
        self.tree = tree  # 保存空间结构树
        self.address = address or {}  # 初始化地址映射
        
        # 如果不是睡眠状态且有居住区域,添加睡觉位置
        if "sleeping" not in self.address and "睡觉" not in self.address and "living_area" in self.address:
            # 将睡觉位置设置为居住区域的床位
            self.address["睡觉"] = self.address["living_area"] + ["床"]

    def __str__(self):
        """将空间结构转换为字符串形式"""
        return utils.dump_dict(self.tree)

    def add_leaf(self, address):
        """向空间树添加新的叶子节点
        address: 地址列表(如['区域1', '子区域1', '位置1'])
        """
        def _add_leaf(left_address, tree):
            """递归添加叶子节点
            left_address: 剩余的地址列表
            tree: 当前子树
            """
            if len(left_address) == 2:  # 如果只剩两级
                # 获取或创建叶子列表
                leaves = tree.setdefault(left_address[0], [])
                # 如果新位置不在列表中,添加它
                if left_address[1] not in leaves:
                    leaves.append(left_address[1])
            elif len(left_address) > 2:  # 如果还有更多层级
                # 递归处理下一层
                _add_leaf(
                    left_address[1:],  # 去掉第一级
                    tree.setdefault(left_address[0], {})  # 获取或创建子树
                )

        _add_leaf(address, self.tree)  # 从根节点开始添加

    def find_address(self, hint, as_list=True):
        """根据提示查找地址
        hint: 地址提示字符串
        as_list: 是否返回列表形式
        返回: 地址列表或字符串
        """
        address = []  # 初始化地址列表
        # 遍历所有已知地址
        for key, path in self.address.items():
            if key in hint:  # 如果提示中包含地址关键字
                address = path  # 使用对应的地址路径
                break
        
        if as_list:  # 如果需要列表形式
            return address  # 直接返回地址列表
        return ":".join(address)  # 否则返回字符串形式

    def get_leaves(self, address):
        """获取指定地址下的所有叶子节点
        address: 地址列表
        返回: 叶子节点列表
        """
        def _get_tree(address, tree):
            """递归获取叶子节点
            address: 剩余地址列表
            tree: 当前子树
            """
            if not address:  # 如果地址列表为空
                if isinstance(tree, dict):  # 如果当前节点是字典
                    return list(tree.keys())  # 返回所有子节点的键
                return tree  # 否则返回叶子节点列表
                
            if address[0] not in tree:  # 如果当前地址不存在
                return []  # 返回空列表
            # 递归处理下一级地址
            return _get_tree(address[1:], tree[address[0]])

        return _get_tree(address, self.tree)  # 从根节点开始查找

    def random_address(self):
        """随机生成一个有效的地址路径
        返回: 随机生成的地址列表
        """
        address, tree = [], self.tree  # 初始化地址列表和当前树
        # 当当前节点是字典时(非叶子节点)
        while isinstance(tree, dict):
            # 获取所有非空的子节点
            roots = [r for r in tree if len(tree[r]) > 0]
            # 随机选择一个子节点
            address.append(random.choice(roots))
            # 移动到选中的子树
            tree = tree[address[-1]]
        # 从最后一级随机选择一个叶子节点
        address.append(random.choice(tree))
        return address  # 返回完整的地址路径
