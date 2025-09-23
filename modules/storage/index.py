"""
这是一个基于LlamaIndex的向量存储类实现。
主要功能:
1. 支持文本向量化存储
2. 提供相似文本检索
3. 支持基于存储内容的问答
"""

# 导入系统和时间相关的包
import os  # 用于文件和路径操作
import time  # 用于延时处理
import threading  # 并发控制
import traceback  # 打印完整错误堆栈

# 导入向量嵌入相关的包
try:
    from llama_index.embeddings.huggingface import HuggingFaceEmbedding  # HuggingFace的文本嵌入模型
except Exception:
    HuggingFaceEmbedding = None
from llama_index.core.indices.vector_store.retrievers import VectorIndexRetriever  # 向量检索器
from llama_index.core.schema import TextNode  # 文本节点数据结构
from llama_index import core as index_core  # LlamaIndex核心功能
try:
    from llama_index.embeddings.ollama import OllamaEmbedding  # Ollama的文本嵌入模型
except Exception:
    OllamaEmbedding = None
from llama_index.core.node_parser import SentenceSplitter  # 文本分句器
from llama_index.core import Settings  # LlamaIndex全局设置
from modules import utils  # 工具函数
try:
    from llama_index.embeddings.google_genai import GoogleGenAIEmbedding
except ImportError:
    GoogleGenAIEmbedding = None

# 尝试导入ZhipuAI embedding (假设存在)
try:
    from llama_index.embeddings.zhipuai import ZhipuAIEmbedding
except ImportError:
    ZhipuAIEmbedding = None # 如果导入失败，将其设为None

class LlamaIndex:
    def __init__(self, embedding, path=None):
        """
        初始化LlamaIndex实例
        Args:
            embedding: 嵌入模型配置,包含type和model等信息
            path: 索引存储路径,如果存在则加载已有索引
        """
        self._config = {"max_nodes": 0}  # 初始化配置,记录最大节点数
        
        # 根据配置选择嵌入模型
        if embedding["type"] == "hugging_face":  # 使用HuggingFace的嵌入模型
            if HuggingFaceEmbedding is None:
                raise NotImplementedError(
                    "HuggingFaceEmbedding is not available. Please install 'llama-index-embeddings-huggingface' if you need this backend."
                )
            embed_model = HuggingFaceEmbedding(model_name=embedding["model"])
        elif embedding["type"] == "ollama":  # 使用Ollama的嵌入模型
            if OllamaEmbedding is None:
                raise NotImplementedError(
                    "OllamaEmbedding is not available. Please install 'llama-index-embeddings-ollama' if you need this backend."
                )
            embed_model = OllamaEmbedding(
                model_name=embedding["model"],
                base_url=embedding["base_url"],
                ollama_additional_kwargs={"mirostat": 0},
            )
        elif embedding["type"] == "zhipuai": # 新增对智谱AI embedding的支持
            if ZhipuAIEmbedding:
                # 假设 ZhipuAIEmbedding 会自动从环境变量 ZHIPUAI_API_KEY 读取密钥
                # 或者需要在这里从 embedding 配置中获取 api_key (如果已传递)
                # model_name 应为 "embedding-2"
                api_key = os.getenv("ZHIPUAI_API_KEY") # 尝试从环境变量获取
                if not api_key and "api_key" in embedding: # 尝试从配置获取 (需要确保配置中传递了key)
                    api_key = embedding["api_key"]
                
                if not api_key:
                    raise ValueError("ZhipuAI API key not found. Please set ZHIPUAI_API_KEY environment variable or provide it in the embedding config.")

                # 确保从 embedding 配置中获取 model 名称
                model_to_use = embedding.get("model") # 直接获取 'model' 的值
                if not model_to_use:
                    # 如果 config.json -> associate.embedding 中没有 'model'，这是个配置问题
                    raise ValueError("ZhipuAI embedding configuration in config.json is missing the 'model' field.")

                embed_model = ZhipuAIEmbedding(
                    model=model_to_use,       # 将 model_name 改为 model
                    api_key=api_key # 显式传递api_key
                    # base_url 通常由SDK内部处理，但如果需要也可以从 embedding["base_url"] 获取并传递
                )
            else:
                raise NotImplementedError(
                    "ZhipuAIEmbedding is not available. Please ensure 'llama-index-embeddings-zhipuai' is installed or ZhipuAI embedding support is correctly configured."
                )
        elif embedding["type"] == "google":
            if GoogleGenAIEmbedding:
                api_key = os.getenv("GOOGLE_API_KEY")
                if not api_key and "api_key" in embedding:
                    api_key = embedding["api_key"]
                
                if not api_key:
                    raise ValueError("Google API key not found. Please set GOOGLE_API_KEY environment variable or provide it in the embedding config.")

                model_to_use = embedding.get("model")
                if not model_to_use:
                    raise ValueError("Google embedding configuration in config.json is missing the 'model' field.")

                embed_model = GoogleGenAIEmbedding(
                    model_name=model_to_use,
                    api_key=api_key
                )
            else:
                raise NotImplementedError(
                    "GoogleGenAIEmbedding is not available. Please ensure 'llama-index-embeddings-google-genai' is installed."
                )
        else:
            raise NotImplementedError(
                "embedding type {} is not supported".format(embedding["type"])
            )

        # 并发保护: 保存专属设置,并通过锁保护全局 Settings 的读写
        self._embed_model = embed_model
        self._node_parser = SentenceSplitter(chunk_size=512, chunk_overlap=64)
        # 类级锁,避免多Agent竞争修改全局 Settings
        if not hasattr(LlamaIndex, "_SETTINGS_LOCK"):
            LlamaIndex._SETTINGS_LOCK = threading.Lock()

        # 配置LlamaIndex全局设置(受锁保护)
        with LlamaIndex._SETTINGS_LOCK:
            Settings.embed_model = self._embed_model  # 设置嵌入模型
            Settings.node_parser = self._node_parser  # 设置文本分句器
            Settings.num_output = 1024  # 设置输出长度限制
            Settings.context_window = 4096  # 设置上下文窗口大小
        
        # 如果指定了路径且存在一个有效的持久化索引 (以 docstore.json 为标志), 则加载已有索引
        docstore_file_path = os.path.join(path, "docstore.json") if path else None
        if path and os.path.exists(docstore_file_path):
            self._index = index_core.load_index_from_storage(
                index_core.StorageContext.from_defaults(persist_dir=path),
                show_progress=True,
            )
            self._config = utils.load_dict(os.path.join(path, "index_config.json"))
        else:  # 否则创建新的空索引
            self._index = index_core.VectorStoreIndex([], show_progress=True)
        self._path = path  # 保存索引路径
        # 统一重试控制(避免无限重试导致卡死)
        self._max_retries = 3
        self._retry_sleep_s = 3.0

    def add_node(
        self,
        text,
        metadata=None,
        exclude_llm_keys=None,
        exclude_embedding_keys=None,
        id=None,
    ):
        """
        向索引中添加新的文本节点
        Args:
            text: 要添加的文本内容
            metadata: 节点的元数据信息,可选
            exclude_llm_keys: 在LLM处理时要排除的元数据键,默认排除所有元数据
            exclude_embedding_keys: 在嵌入处理时要排除的元数据键,默认排除所有元数据
            id: 节点ID,如果不指定则自动生成
        Returns:
            添加的TextNode节点对象
        """
        attempts = 0
        while True:  # 有限重试
            try:
                metadata = metadata or {}  # 如果没有提供元数据,使用空字典
                # 默认排除所有元数据键
                exclude_llm_keys = exclude_llm_keys or list(metadata.keys())
                exclude_embedding_keys = exclude_embedding_keys or list(metadata.keys())

                # 生成节点ID,格式为"node_序号"
                id = id or "node_" + str(self._config["max_nodes"])
                self._config["max_nodes"] += 1  # 更新最大节点数

                # 创建文本节点
                node = TextNode(
                    text=text,  # 节点文本内容
                    id_=id,  # 节点ID
                    metadata=metadata,  # 节点元数据
                    excluded_llm_metadata_keys=exclude_llm_keys,  # LLM处理时排除的元数据键
                    excluded_embed_metadata_keys=exclude_embedding_keys,  # 嵌入处理时排除的元数据键
                )
                # 插入节点(需要确保 Settings 使用本实例的 embed_model)
                with LlamaIndex._SETTINGS_LOCK:
                    Settings.embed_model = self._embed_model
                    Settings.node_parser = self._node_parser
                    self._index.insert_nodes([node])  # 将节点插入索引
                return node
            except Exception as e:  # 捕获所有异常
                attempts += 1
                print(f"LlamaIndex.add_node() caused an error: {e} ({type(e).__name__})")
                traceback.print_exc()
                if attempts >= self._max_retries:
                    raise  # 节点添加失败应抛出,由上层处理
                time.sleep(self._retry_sleep_s)  # 出错后等待再重试

    def has_node(self, node_id):
        """
        检查指定ID的节点是否存在
        Args:
            node_id: 要检查的节点ID
        Returns:
            bool: 节点是否存在
        """
        return node_id in self._index.docstore.docs  # 在文档存储中查找节点ID

    def find_node(self, node_id):
        """
        查找并返回指定ID的节点
        Args:
            node_id: 要查找的节点ID
        Returns:
            TextNode: 找到的节点对象
        """
        return self._index.docstore.docs[node_id]  # 从文档存储中获取节点

    def get_nodes(self, filter=None):
        """
        获取所有节点,可以通过filter函数进行过滤
        Args:
            filter: 可选的过滤函数,接收节点作为参数,返回bool值
        Returns:
            list: 符合条件的节点列表
        """
        def _check(node):
            if not filter:  # 如果没有过滤函数
                return True  # 返回所有节点
            return filter(node)  # 使用过滤函数判断

        return [n for n in self._index.docstore.docs.values() if _check(n)]  # 列表推导式获取符合条件的节点

    def remove_nodes(self, node_ids, delete_from_docstore=True):
        """
        删除指定ID的节点
        Args:
            node_ids: 要删除的节点ID列表
            delete_from_docstore: 是否从文档存储中彻底删除
        """
        self._index.delete_nodes(node_ids, delete_from_docstore=delete_from_docstore)

    def cleanup(self):
        """
        清理过期的节点
        Returns:
            list: 被删除的节点ID列表
        """
        now, remove_ids = utils.get_timer().get_date(), []  # 获取当前时间
        for node_id, node in self._index.docstore.docs.items():
            create = utils.to_date(node.metadata["create"])  # 获取节点创建时间
            expire = utils.to_date(node.metadata["expire"])  # 获取节点过期时间
            if create > now or expire < now:  # 如果节点未创建或已过期
                remove_ids.append(node_id)  # 添加到待删除列表
        self.remove_nodes(remove_ids)  # 删除过期节点
        return remove_ids  # 返回删除的节点ID列表

    def retrieve(
        self,
        text,
        similarity_top_k=5,
        filters=None,
        node_ids=None,
        retriever_creator=None,
    ):
        """
        检索与给定文本相似的节点
        Args:
            text: 查询文本
            similarity_top_k: 返回最相似的前k个结果
            filters: 过滤条件
            node_ids: 限定检索范围的节点ID列表
            retriever_creator: 自定义检索器创建函数
        Returns:
            检索结果列表
        """
        attempts = 0
        # 防御: top_k 至少为 1
        similarity_top_k = max(1, int(similarity_top_k) if similarity_top_k is not None else 1)
        while True:  # 有限重试
            try:
                retriever_creator = retriever_creator or VectorIndexRetriever  # 使用默认或自定义的检索器
                # 确保全局 Settings 与本实例一致,并串行化 embed_model 的切换
                with LlamaIndex._SETTINGS_LOCK:
                    Settings.embed_model = self._embed_model
                    Settings.node_parser = self._node_parser
                    retriever = retriever_creator(
                        self._index,
                        similarity_top_k=similarity_top_k,  # 设置返回结果数量
                        filters=filters,  # 设置过滤条件
                        node_ids=node_ids,  # 设置检索范围
                    )
                    return retriever.retrieve(text)  # 执行检索
            except Exception as e:  # 捕获所有异常
                attempts += 1
                print(f"LlamaIndex.retrieve() caused an error: {e} ({type(e).__name__})")
                traceback.print_exc()
                if attempts >= self._max_retries:
                    print("LlamaIndex.retrieve() giving up after max retries, returning empty list.")
                    return []
                time.sleep(self._retry_sleep_s)  # 出错后等待再重试

    def query(
        self,
        text,
        similarity_top_k=5,
        text_qa_template=None,
        refine_template=None,
        filters=None,
        query_creator=None,
    ):
        """
        基于存储的内容回答查询
        Args:
            text: 查询文本
            similarity_top_k: 使用最相似的前k个结果
            text_qa_template: 问答模板
            refine_template: 答案优化模板
            filters: 过滤条件
            query_creator: 自定义查询引擎创建函数
        Returns:
            查询结果
        """
        kwargs = {
            "similarity_top_k": similarity_top_k,  # 设置相似度检索数量
            "text_qa_template": text_qa_template,  # 设置问答模板
            "refine_template": refine_template,  # 设置优化模板
            "filters": filters,  # 设置过滤条件
        }
        attempts = 0
        while True:  # 有限重试
            try:
                # 确保全局 Settings 与本实例一致
                with LlamaIndex._SETTINGS_LOCK:
                    Settings.embed_model = self._embed_model
                    Settings.node_parser = self._node_parser
                    if query_creator:  # 如果提供了自定义查询引擎创建函数
                        query_engine = query_creator(retriever=self._index.as_retriever(**kwargs))
                    else:  # 使用默认查询引擎
                        query_engine = self._index.as_query_engine(**kwargs)
                    return query_engine.query(text)  # 执行查询
            except Exception as e:  # 捕获所有异常
                attempts += 1
                print(f"LlamaIndex.query() caused an error: {e} ({type(e).__name__})")
                traceback.print_exc()
                if attempts >= self._max_retries:
                    raise
                time.sleep(self._retry_sleep_s)  # 出错后等待再重试

    def save(self, path=None):
        """
        保存索引到指定路径
        Args:
            path: 保存路径,如果为None则使用初始化时的路径
        """
        path = path or self._path  # 使用指定路径或默认路径
        self._index.storage_context.persist(path)  # 持久化存储索引
        utils.save_dict(self._config, os.path.join(path, "index_config.json"))  # 保存配置信息

    @property
    def nodes_num(self):
        """
        获取索引中的节点数量
        Returns:
            int: 节点总数
        """
        return len(self._index.docstore.docs)  # 返回文档存储中的节点数量

