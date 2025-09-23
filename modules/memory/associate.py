"""
这个模块实现了代理人的记忆关联系统:
1. Concept类 - 表示一个记忆概念,包含事件、重要性和时间信息
2. AssociateRetriever类 - 实现记忆检索的逻辑
3. Associate类 - 管理代理人的整体记忆系统
"""

import datetime  # 导入日期时间处理模块
from llama_index.core.retrievers import BaseRetriever  # 导入基础检索器类
from llama_index.core.vector_stores import MetadataFilters, ExactMatchFilter  # 导入向量存储过滤器
from llama_index.core.indices.vector_store.retrievers import VectorIndexRetriever  # 导入向量索引检索器

from modules.storage.index import LlamaIndex  # 导入LlamaIndex存储系统
from modules import utils  # 导入工具函数
from .event import Event  # 导入事件类


class Concept:
    """概念类,表示代理人记忆中的一个具体概念"""
    
    def __init__(
        self,
        describe,  # 概念描述
        node_id,  # 节点ID
        node_type,  # 节点类型(event/thought/chat)
        subject,  # 主体
        predicate,  # 谓语
        object,  # 对象
        address,  # 地址
        poignancy,  # 重要性分数
        create=None,  # 创建时间
        expire=None,  # 过期时间
        access=None,  # 最后访问时间
    ):
        """初始化一个概念
        describe: 概念的文字描述
        node_id: 唯一标识符
        node_type: 节点类型
        subject/predicate/object: 事件的主谓宾
        address: 地址字符串(用:分隔)
        poignancy: 重要性分数
        create/expire/access: 时间相关字段
        """
        self.node_id = node_id  # 保存节点ID
        self.node_type = node_type  # 保存节点类型
        # 创建事件对象(将地址字符串分割为列表)
        self.event = Event(
            subject, predicate, object, describe=describe, address=address.split(":")
        )
        self.poignancy = poignancy  # 保存重要性分数
        # 设置创建时间(如果提供则解析,否则使用当前时间)
        self.create = utils.to_date(create) if create else utils.get_timer().get_date()
        # 设置过期时间
        if expire:
            self.expire = utils.to_date(expire)  # 如果提供则解析
        else:
            # 默认30天后过期
            self.expire = self.create + datetime.timedelta(days=30)
        # 设置最后访问时间(如果提供则解析,否则使用创建时间)
        self.access = utils.to_date(access) if access else self.create

    def abstract(self):
        """生成概念的摘要信息
        返回: 包含概念类型、重要性和时间信息的字典
        """
        return {
            # 格式化显示概念类型和重要性分数
            "{}(P.{})".format(self.node_type, self.poignancy): str(self.event),
            # 格式化显示时间信息
            "duration": "{} ~ {} (access: {})".format(
                self.create.strftime("%Y%m%d-%H:%M"),  # 创建时间
                self.expire.strftime("%Y%m%d-%H:%M"),  # 过期时间
                self.access.strftime("%Y%m%d-%H:%M"),  # 访问时间
            ),
        }

    def __str__(self):
        """将概念转换为字符串形式"""
        return utils.dump_dict(self.abstract())

    @property
    def describe(self):
        """获取概念的描述文本"""
        return self.event.get_describe()

    @classmethod
    def from_node(cls, node):
        """从存储节点创建概念实例
        node: 存储节点对象
        返回: 新的Concept实例
        """
        return cls(node.text, node.id_, **node.metadata)

    @classmethod
    def from_event(cls, node_id, node_type, event, poignancy):
        """从事件创建概念例
        node_id: 节点ID
        node_type: 节点类型
        event: 事件对象
        poignancy: 重要性分数
        返回: 新的Concept实例
        """
        return cls(
            event.get_describe(),  # 获取事件描述
            node_id,  # 节点ID
            node_type,  # 节点类型
            event.subject,  # 事件主体
            event.predicate,  # 事件谓语
            event.object,  # 事件对象
            ":".join(event.address),  # 连接地址列表
            poignancy,  # 重要性分数
        )


class AssociateRetriever(BaseRetriever):
    """记忆检索器类,实现基于相关性、时间和重要性的记忆检索"""
    
    def __init__(self, config, *args, **kwargs) -> None:
        """初始化检索器
        config: 检索配置,包含衰减因子和权重设置
        """
        self._config = config  # 保存配置
        # 创建向量检索器实例
        self._vector_retriever = VectorIndexRetriever(*args, **kwargs)
        super().__init__()  # 调用父类初始化

    def _retrieve(self, query_bundle):
        """执行记忆检索
        query_bundle: 查询包,包含查询文本
        返回: 检索到的节点列表
        """
        # 使用向量检索器获取初始结果
        nodes = self._vector_retriever.retrieve(query_bundle)
        if not nodes:  # 如果没有结果则返回空列表
            return []
            
        # 按最后访问时间排序(最近访问的优先)
        nodes = sorted(
            nodes, 
            key=lambda n: utils.to_date(n.metadata["access"]), 
            reverse=True
        )

        # 计算各种分数
        fac = self._config["recency_decay"]  # 时间衰减因子
        # 计算时间衰减分数(越早的记忆分数越低)
        recency_scores = self._normalize(
            [fac**i for i in range(1, len(nodes) + 1)],
            self._config["recency_weight"]  # 时间权重
        )
        # 计算相关性分数(基于向量相似度)
        relevance_scores = self._normalize(
            [n.score for n in nodes],
            self._config["relevance_weight"]  # 相关性权重
        )
        # 计算重要性分数
        importance_scores = self._normalize(
            [n.metadata["poignancy"] for n in nodes],
            self._config["importance_weight"]  # 重要性权重
        )
        
        # 计算每个节点的最终分数(三种分数的加权和)
        final_scores = {
            n.id_: r1 + r2 + i
            for n, r1, r2, i in zip(
                nodes, recency_scores, relevance_scores, importance_scores
            )
        }

        # 根据最终分数重新排序节点
        nodes = sorted(nodes, key=lambda n: final_scores[n.id_], reverse=True)
        # 只保留指定数量的最高分节点
        nodes = nodes[: self._config["retrieve_max"]]
        # 更新所有返回节点的访问时间
        for n in nodes:
            n.metadata["access"] = utils.get_timer().get_date("%Y%m%d-%H:%M:%S")
        return nodes

    def _normalize(self, data, factor=1, t_min=0, t_max=1):
        """归一化数据到指定范围
        data: 要归一化的数据列表
        factor: 权重因子
        t_min/t_max: 目标范围
        返回: 归一化后的数据列表
        """
        min_val, max_val = min(data), max(data)  # 获取数据范围
        diff = max_val - min_val  # 计算数据跨度
        if diff == 0:  # 如果所有值相同
            # 返回中间值
            return [(t_max - t_min) * factor / 2 for _ in data]
        # 执行归一化计算
        return [(d - min_val) * (t_max - t_min) * factor / diff + t_min for d in data]


class Associate:
    """记忆关联系统类,管理代理人的整体记忆"""
    
    def __init__(
        self,
        path,  # 存储路径
        embedding_config,  # 嵌入模型配置 (原 embedding)
        api_keys,          # 新增: API密钥
        retention=8,  # 忆保留数量
        max_memory=-1,  # 最大记忆数量(-1表示无限)
        max_importance=10,  # 最大重要性分数
        recency_decay=0.995,  # 时间衰减因子
        recency_weight=0.5,  # 时间权重
        relevance_weight=3,  # 相关性权重
        importance_weight=2,  # 重要性权重
        memory=None,  # 初始记忆
    ):
        """初始化记忆关联系统
        path: 存储路径
        embedding_config: 包含type, model等信息的嵌入配置字典
        api_keys: 包含各种服务API Key的字典
        retention: 每次检索返回的记忆数量
        max_memory: 最大记忆容量
        max_importance: 重要性分数上限
        recency_decay: 时间衰减因子
        recency/relevance/importance_weight: 各维度的权重
        memory: 初始记忆数据
        """
        # 准备传递给 LlamaIndex 的 embedding 配置
        final_embedding_config = embedding_config.copy()

        if final_embedding_config.get("type") == "zhipuai":
            if "ZHIPUAI_API_KEY" in api_keys and api_keys["ZHIPUAI_API_KEY"]:
                # LlamaIndex 的 ZhipuAIEmbedding 通常期望 api_key 参数
                final_embedding_config["api_key"] = api_keys["ZHIPUAI_API_KEY"]
            else:
                # 如果 ZHIPUAI_API_KEY 缺失, LlamaIndex 初始化时会抛出错误
                # 我们也可以在这里提前抛出，或者让 LlamaIndex 处理
                pass 

        # 保存索引配置
        self._index_config = {"embedding": final_embedding_config, "path": path}
        # 创建索引实例
        self._index = LlamaIndex(**self._index_config)
        # 初始化记忆字典(按类型分类)
        self.memory = memory or {"event": [], "thought": [], "chat": []}
        self.cleanup_index()  # 清理过期索引

        # 保存基本参数
        self.retention = retention  # 记忆保留数量
        self.max_memory = max_memory  # 最大记忆容量
        self.max_importance = max_importance  # 最大重要性分数
        
        # 设置检索配置
        self._retrieve_config = {
            "recency_decay": recency_decay,  # 时间衰减因子
            "recency_weight": recency_weight,  # 时间权重
            "relevance_weight": relevance_weight,  # 相关性权重
            "importance_weight": importance_weight,  # 重要性权重
        }

    def abstract(self):
        """生成记忆系统的摘要信息
        返回: 包含节点数量和各类型记忆描述的字典
        """
        des = {"nodes": self._index.nodes_num}  # 记录总节点数
        # 获取每种类型记忆的描述
        for t in ["event", "chat", "thought"]:
            des[t] = [self.find_concept(c).describe for c in self.memory[t]]
        return des

    def __str__(self):
        """将记忆系统转换为字符串形式"""
        return utils.dump_dict(self.abstract())

    def cleanup_index(self):
        """清理过期的索引节点"""
        # 删除过期节点并获取被删除的节点ID
        node_ids = self._index.cleanup()
        # 从记忆列表中移除被删除的节点
        self.memory = {
            n_type: [n for n in nodes if n not in node_ids]
            for n_type, nodes in self.memory.items()
        }

    def add_node(
        self,
        node_type,  # 节点类型
        event,  # 事件对象
        poignancy,  # 重要性分数
        create=None,  # 创建时间
        expire=None,  # 过期时间
        filling=None,  # 填充信息(未使用)
    ):
        """添加新的记忆节点
        node_type: 节点类型(event/thought/chat)
        event: 事件对象
        poignancy: 重要性分数
        create/expire: 时间相关字段
        返回: 创建的概念对象
        """
        # 设置创建时间和过期时间
        create = create or utils.get_timer().get_date()
        expire = expire or (create + datetime.timedelta(days=30))
        
        # 准备节点元数据
        metadata = {
            "node_type": node_type,  # 节点类型
            "subject": event.subject,  # 事件主体
            "predicate": event.predicate,  # 事件谓语
            "object": event.object,  # 事件对象
            "address": ":".join(event.address),  # 地址字符串
            "poignancy": poignancy,  # 重要性分数
            "create": create.strftime("%Y%m%d-%H:%M:%S"),  # 创建时间
            "expire": expire.strftime("%Y%m%d-%H:%M:%S"),  # 过期时间
            "access": create.strftime("%Y%m%d-%H:%M:%S"),  # 访问时间
        }

        # 添加节点到索引中(容错)
        try:
            node = self._index.add_node(event.get_describe(), metadata)
        except Exception as e:
            print(f"Associate.add_node() failed: {e} ({type(e).__name__})")
            return None
        if not node:
            return None
        # 获取对应类型的记忆列表
        memory = self.memory[node_type]
        # 将新节点ID插入到列表开头
        memory.insert(0, node.id_)
        
        # 如果超过最大记忆容量限制
        if len(memory) >= self.max_memory > 0:
            # 删除多余的节点
            self._index.remove_nodes(memory[self.max_memory:])
            # 保留容量限制内的记忆
            self.memory[node_type] = memory[: self.max_memory - 1]
        # 返回创建的概念对象
        return self.to_concept(node)

    def to_concept(self, node):
        """将存储节点转换为概念对象
        node: 存储节点
        返回: Concept实例
        """
        return Concept.from_node(node)

    def find_concept(self, node_id):
        """根据节点ID查找概念
        node_id: 节点ID
        返回: Concept实例
        """
        return self.to_concept(self._index.find_node(node_id))

    def _retrieve_nodes(self, node_type, text=None):
        """检索指定类型的记忆节点
        node_type: 节点类型
        text: 搜索文本(可选)
        返回: 检索到的概念列表
        """
        if text:  # 如果提供了搜索文本
            # 创建类型过滤器
            filters = MetadataFilters(
                filters=[ExactMatchFilter(key="node_type", value=node_type)]
            )
            # 执行文本搜索
            node_ids = self.memory[node_type]
            if not node_ids:  # 空集合直接返回
                nodes = []
            else:
                nodes = self._index.retrieve(
                    text, filters=filters, node_ids=node_ids
                )
        else:
            # 否则直接获取所有节点
            nodes = [self._index.find_node(n) for n in self.memory[node_type]]
        # 转换为概念对象并限制返回数量
        return [self.to_concept(n) for n in nodes[: self.retention]]

    def retrieve_events(self, text=None):
        """检索事件类型的记忆
        text: 搜索文本(可选)
        返回: 事件概念列表
        """
        return self._retrieve_nodes("event", text)

    def retrieve_thoughts(self, text=None):
        """检索思考类型的记忆
        text: 搜索文本(可选)
        返回: 思考概念列表
        """
        return self._retrieve_nodes("thought", text)

    def retrieve_chats(self, name=None):
        """检索对话类型的记忆
        name: 对话对象名称(可选)
        返回: 对话概念列表
        """
        text = ("对话 " + name) if name else None
        return self._retrieve_nodes("chat", text)

    def retrieve_focus(self, focus, retrieve_max=30, reduce_all=True):
        """检索与关注点相关的记忆
        focus: 关注点文本或列表
        retrieve_max: 每个关注点返回的最大记忆数量
        reduce_all: 是否合并所有关注点的结果
        返回: 检索到的概念列表或按关注点分组的字典
        """
        # 创建检索器工厂函数
        def _create_retriever(*args, **kwargs):
            self._retrieve_config["retrieve_max"] = retrieve_max
            return AssociateRetriever(self._retrieve_config, *args, **kwargs)

        retrieved = {}  # 存储检索结果
        # 获取事件和思考类型的所有节点ID
        node_ids = self.memory["event"] + self.memory["thought"]
        if not node_ids:
            return [] if reduce_all else {}
        
        # 遍历每个关注点进行检索
        for text in focus:
            # 执行检索
            nodes = self._index.retrieve(
                text,
                similarity_top_k=len(node_ids),
                node_ids=node_ids,
                retriever_creator=_create_retriever,
            )
            if reduce_all:  # 如果需要合并结果
                retrieved.update({n.id_: n for n in nodes})  # 使用字典去重
            else:
                retrieved[text] = nodes  # 保存每个关注点的结果

        if reduce_all:  # 如果合并结果
            return [self.to_concept(v) for v in retrieved.values()]
        # 否则返回按关注点分组的结果
        return {
            text: [self.to_concept(n) for n in nodes]
            for text, nodes, in retrieved.items()
        }

    def get_relation(self, node):
        """获取节点的相关记忆
        node: 概念节点
        返回: 包含相关事件和思考的字典
        """
        return {
            "node": node,  # 原始节点
            "events": self.retrieve_events(node.describe),  # 相关事件
            "thoughts": self.retrieve_thoughts(node.describe),  # 相关思考
        }

    def to_dict(self):
        """将记忆系统转换为字典形式(用于序列化)
        返回: 包含记忆数据的字典
        """
        self._index.save()  # 保存索引
        return {"memory": self.memory}  # 返回记忆数据

    @property
    def index(self):
        """获取底层索引实例"""
        return self._index
