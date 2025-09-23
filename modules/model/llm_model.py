"""
这是一个LLM(大语言模型)的实现文件,包含了与各种LLM模型交互的基类和具体实现类。
主要功能:
1. 提供统一的模型接口(embedding和completion)
2. 支持多种模型后端(OpenAI、Ollama、智谱AI等)
3. 处理API调用的重试、错误处理等
"""

# 导入所需的Python标准库
import os        # 用于操作系统相关功能,如环境变量
import time      # 用于时间相关操作,如延迟
import re        # 用于正则表达式处理
import json      # 用于JSON数据处理
import requests  # 用于发送HTTP请求

# 导入项目内部模块
from modules.utils.namespace import ModelType  # 导入模型类型枚举
from modules import utils                      # 导入工具函数

class ModelStyle:
    """
    模型风格类 - 定义了支持的不同LLM服务提供商
    使用类变量来定义各种模型类型的标识符
    """
    OPEN_AI = "openai"      # OpenAI API服务
    QIANFAN = "qianfan"     # 百度千帆大模型服务
    SPARK_AI = "sparkai"    # 讯飞星火大模型服务
    ZHIPU_AI = "zhipuai"    # 智谱AI服务
    GEMINI = "google"      # Google Gemini 服务
    OLLAMA = "ollama"       # Ollama本地模型服务

class LLMModel:
    """
    LLM模型的基类,定义了与大语言模型交互的基本接口和功能
    包含:初始化配置、embedding生成、文本补全等核心功能
    """
    def __init__(self, base_url, model, embedding_model, keys, config=None):
        """
        初始化LLM模型
        Args:
            base_url (str): API基础URL
            model (str): 模型名称
            embedding_model (str): 用于生成embedding的模型名称
            keys (dict): API密钥信息
            config (dict, optional): 额外配置信息
        """
        self._base_url = base_url                    # 存储API基础URL
        self._model = model                          # 存储模型名称
        self._embedding_model = embedding_model      # 存储embedding模型名称
        self._handle = self.setup(keys, config)      # 初始化模型句柄
        self._meta_responses = []                    # 存储元响应信息
        self._summary = {"total": [0, 0, 0]}        # 初始化统计信息
        self._enabled = True                         # 模型启用状态标志

    def embedding(self, text, retry=10):
        """
        生成文本的embedding向量表示,支持失败重试
        
        Args:
            text (str): 需要生成embedding的文本
            retry (int): 失败重试次数,默认10次
            
        Returns:
            list: 文本的embedding向量,如果全部重试失败则返回None
        """
        response = None                          # 初始化响应为空
        for _ in range(retry):                   # 最多重试retry次
            try:
                response = self._embedding(text)  # 调用具体的embedding实现
            except Exception as e:               # 捕获所有可能的异常
                print(f"LLMModel.embedding() caused an error: {e}")  # 打印错误信息
                time.sleep(5)                    # 失败后等待5秒再重试
                continue
            if response:                         # 如果获得了有效响应
                break                           # 退出重试循环
        return response                         # 返回embedding结果

    def _embedding(self, text):
        """
        生成embedding的具体实现方法
        这是一个基类方法,需要在子类中实现具体的embedding生成逻辑
        
        Args:
            text (str): 需要生成embedding的文本
            
        Raises:
            NotImplementedError: 基类中该方法为空,子类必须实现
        """
        raise NotImplementedError(
            "_embedding is not support for " + str(self.__class__)  # 提示该方法需要在子类中实现
        )

    def completion(
        self,
        prompt,
        retry=10,
        callback=None,
        failsafe=None,
        caller="llm_normal",
        **kwargs
    ):
        """
        执行文本补全/生成任务,支持重试和回调处理
        
        Args:
            prompt (str): 输入提示文本
            retry (int): 失败重试次数,默认10次
            callback (callable, optional): 处理模型响应的回调函数
            failsafe: 当所有重试都失败时的返回值
            caller (str): 调用者标识,用于统计分类,默认"llm_normal"
            **kwargs: 传递给_completion的额外参数
            
        Returns:
            根据callback返回处理后的结果,如果失败则返回failsafe值
        """
        response, self._meta_responses = None, []     # 初始化响应和元响应列表
        self._summary.setdefault(caller, [0, 0, 0])  # 确保caller的统计项存在
        
        for _ in range(retry):                       # 最多重试retry次
            try:
                # 调用具体的completion实现
                meta_response = self._completion(prompt, **kwargs)
                # 记录元响应
                self._meta_responses.append(meta_response)
                # 更新总调用次数统计
                self._summary["total"][0] += 1
                # 更新特定caller的调用次数
                self._summary[caller][0] += 1
                
                # 如果有回调函数,使用回调处理响应
                if callback:
                    response = callback(meta_response)
                else:
                    response = meta_response
                    
            except Exception as e:                    # 捕获所有可能的异常
                print(f"LLMModel.completion() caused an error: {e}")
                time.sleep(5)                         # 失败后等待5秒
                response = None
                continue
                
            if response is not None:                 # 如果获得了有效响应
                break                                # 退出重试循环
                
        # 更新成功/失败统计
        pos = 2 if response is None else 1           # 2表示失败,1表示成功
        self._summary["total"][pos] += 1             # 更新总统计
        self._summary[caller][pos] += 1              # 更新caller统计
        
        return response or failsafe                  # 返回响应或failsafe值

    def _completion(self, prompt, **kwargs):
        """
        文本补全的具体实现方法
        这是一个基类方法,需要在子类中实现具体的补全生成逻辑
        
        Args:
            prompt (str): 输入提示文本
            **kwargs: 额外的参数
            
        Raises:
            NotImplementedError: 基类中该方法为空,子类必须实现
        """
        raise NotImplementedError(
            "_completion is not support for " + str(self.__class__)
        )

    def is_available(self):
        """
        检查模型是否可用
        
        Returns:
            bool: 如果模型启用且错误次数在可接受范围内返回True,否则返回False
        """
        return self._enabled  # 返回模型启用状态

    def get_summary(self):
        """
        获取模型使用统计信息的摘要
        
        Returns:
            dict: 包含模型名称和统计信息的字典
                 格式: {
                     "model": 模型名称,
                     "summary": {
                         调用者: "成功数,失败数/总请求数"
                     }
                 }
        """
        des = {}
        for k, v in self._summary.items():
            des[k] = "S:{},F:{}/R:{}".format(v[1], v[2], v[0])  # 格式化统计信息
        return {"model": self._model, "summary": des}

    def disable(self):
        """
        禁用模型
        设置_enabled为False,使模型不再接受新的请求
        """
        self._enabled = False

    @property
    def meta_responses(self):
        """
        获取模型的元响应列表
        
        Returns:
            list: 包含模型原始响应的列表
        """
        return self._meta_responses

    @classmethod
    def model_type(cls):
        """
        获取模型类型
        
        Returns:
            ModelType: 返回LLM类型标识
        """
        return ModelType.LLM

    @classmethod
    def support_model(cls, model):
        """
        检查是否支持指定的模型
        
        Args:
            model (str): 模型名称
            
        Returns:
            bool: 如果支持该模型返回True,否则返回False
        """
        return model in ("gpt-3.5-turbo", "text-embedding-3-small")  # 当前支持的OpenAI模型列表

    @classmethod
    def creatable(cls, keys, config):
        """
        检查是否可以创建模型实例
        
        Args:
            keys (dict): 密钥信息
            config (dict): 配置信息
            
        Returns:
            bool: 如果包含必要的API密钥返回True,否则返回False
        """
        return "OPENAI_API_KEY" in keys  # 检查是否包含OpenAI API密钥

    @classmethod
    def model_style(cls):
        """
        获取模型风格
        
        Returns:
            str: 返回"openai"表示OpenAI风格
        """
        return ModelStyle.OPEN_AI

@utils.register_model  # 注册模型装饰器,用于模型注册管理
class OpenAILLMModel(LLMModel):
    """
    OpenAI API模型的具体实现类
    支持GPT系列模型的文本生成和embedding生成
    """
    
    def setup(self, keys, config):
        """
        初始化OpenAI客户端
        
        Args:
            keys (dict): 包含API密钥的字典
            config (dict): 配置信息
            
        Returns:
            OpenAI: 初始化好的OpenAI客户端实例
        """
        from openai import OpenAI  # 导入OpenAI客户端

        # 设置embedding模型,默认使用text-embedding-3-small
        self._embedding_model = config.get("embedding_model", "text-embedding-3-small")
        # 使用API密钥初始化客户端
        return OpenAI(api_key=keys["OPENAI_API_KEY"])

    def _embedding(self, text):
        """
        使用OpenAI API生成文本的embedding
        
        Args:
            text (str): 输入文本
            
        Returns:
            list: 文本的embedding向量
        """
        # 调用OpenAI embeddings API
        response = self._handle.embeddings.create(
            input=text, model=self._embedding_model
        )
        # 返回第一个结果的embedding向量
        return response.data[0].embedding

    def _completion(self, prompt, temperature=0.00001):
        """
        使用OpenAI API生成文本补全
        
        Args:
            prompt (str): 输入提示文本
            temperature (float): 采样温度,控制输出的随机性,默认接近0表示确定性输出
            
        Returns:
            str: 模型生成的文本
        """
        # 构造消息格式
        messages = [{"role": "user", "content": prompt}]
        # 调用OpenAI chat completions API
        response = self._handle.chat.completions.create(
            model=self._model, messages=messages, temperature=temperature
        )
        # 如果有选择返回第一个选择的内容,否则返回空字符串
        content_to_return = ""
        if len(response.choices) > 0:
            content_to_return = response.choices[0].message.content
        
        print(f"[MY_DEBUG] OpenAILLMModel._completion is returning: '{content_to_return}'")
        return content_to_return

@utils.register_model
class OllamaLLMModel(LLMModel):
    """
    Ollama本地模型的具体实现类
    支持各种开源模型的本地部署和调用
    """
    
    def setup(self, keys, config):
        """
        初始化Ollama配置
        由于是本地部署,不需要API密钥
        
        Args:
            keys (dict): 密钥信息(未使用)
            config (dict): 配置信息(未使用)
            
        Returns:
            None: Ollama不需要特殊的客户端实例
        """
        return None

    def ollama_chat(self, messages, temperature, stream):
        """
        调用Ollama的chat接口
        
        Args:
            messages (list): 对话消息列表
            temperature (float): 采样温度
            stream (bool): 是否使用流式响应
            
        Returns:
            dict: Ollama API的响应结果
        """
        headers = {
            "Content-Type": "application/json"
        }
        params = {
            "model": self._model,
            "messages": messages,
            "temperature": temperature,
            "stream": stream,
        }

        # 发送POST请求到Ollama API
        response = requests.post(
            url=f"{self._base_url}/chat/completions",
            headers=headers,
            json=params,
            stream=stream
        )
        return response.json()

    def ollama_embeddings(self, text):
        """
        调用Ollama的embeddings接口
        
        Args:
            text (str): 输入文本
            
        Returns:
            dict: Ollama API的响应结果
        """
        headers = {
            "Content-Type": "application/json"
        }
        params = {
            "model": self._embedding_model,
            "input": text,
        }

        # 发送POST请求到Ollama API
        response = requests.post(
            url=f"{self._base_url}/embeddings",
            headers=headers,
            json=params,
        )
        return response.json()

    def _embedding(self, text):
        """
        生成文本的embedding向量
        
        Args:
            text (str): 输入文本
            
        Returns:
            list: 文本的embedding向量
        """
        response = self.ollama_embeddings(text)
        return response["data"][0]["embedding"]

    def _completion(self, prompt, temperature=0.00001):
        """
        生成文本补全
        
        Args:
            prompt (str): 输入提示文本
            temperature (float): 采样温度,默认接近0表示确定性输出
            
        Returns:
            str: 生成的文本
        """
        messages = [{"role": "user", "content": prompt}]
        response = self.ollama_chat(messages=messages, temperature=temperature, stream=False)
        content_to_return = ""
        if response and len(response["choices"]) > 0:
            content_to_return = response["choices"][0]["message"]["content"]
        
        print(f"[MY_DEBUG] OllamaLLMModel._completion is returning: '{content_to_return}'")
        return content_to_return

    @classmethod
    def support_model(cls, model):
        """
        检查是否支持指定的模型
        Ollama支持所有已安装的模型
        
        Args:
            model (str): 模型名称
            
        Returns:
            bool: 始终返回True
        """
        return True  # Ollama支持所有已安装的模型

    @classmethod
    def creatable(cls, keys, config):
        """
        检查是否可以创建模型实例
        Ollama是本地部署,需要检查config中是否包含有效的Ollama base_url
        
        Args:
            keys (dict): 密钥信息
            config (dict): 配置信息 (通常是 agent.think.llm 的内容)
            
        Returns:
            bool: 如果配置了有效的Ollama base_url则返回True,否则返回False
        """
        if config and "base_url" in config and config["base_url"]:
            # 检查 base_url 是否包含典型的本地Ollama服务地址特征
            # 或其他你认为合适的Ollama URL特征
            url_lower = config["base_url"].lower()
            if "127.0.0.1" in url_lower or "localhost" in url_lower or "ollama" in url_lower:
                return True
        return False # 如果没有提供有效的Ollama base_url，则不可创建

    @classmethod
    def model_style(cls):
        """
        获取模型风格
        
        Returns:
            str: 返回"ollama"示Ollama风格
        """
        return ModelStyle.OLLAMA

@utils.register_model
class ZhipuAILLMModel(LLMModel):
    """
    智谱AI大模型的具体实现类
    支持GLM系列模型的文本生成和embedding生成
    """
    
    def setup(self, keys, config):
        """
        初始化智谱AI客户端
        
        Args:
            keys (dict): 包含API密钥的字典
            config (dict): 配置信息
            
        Returns:
            ZhipuAI: 初始化好的智谱AI客户端实例
        """
        from zhipuai import ZhipuAI  # 导入智谱AI的Python SDK

        return ZhipuAI(api_key=keys["ZHIPUAI_API_KEY"])  # 使用API密钥初始化客户端

    def _embedding(self, text):
        """
        使用智谱AI API生成文本的embedding
        
        Args:
            text (str): 输入文本
            
        Returns:
            list: 文本的embedding向量
        """
        # 调用智谱AI embeddings API,使用 self._embedding_model (来自config.json的配置)
        response = self._handle.embeddings.create(model=self._embedding_model, input=text)
        # 返回第一个结果的embedding向量
        return response.data[0].embedding

    def _completion(self, prompt, temperature=0.7):
        """
        使用智谱AI API生成文本补全
        
        Args:
            prompt (str): 输入提示文本
            temperature (float): 采样温度,控制输出的随机性,默认接近0表示确定性输出
            
        Returns:
            str: 生成的文本
        """
        # 构造消息格式
        messages = [{"role": "user", "content": prompt}]
        # 调用智谱AI chat completions API
        response = self._handle.chat.completions.create(
            model=self._model,          # 使用指定的模型
            messages=messages,          # 传入消息列表
            temperature=temperature     # 设置采样温度
        )
        # 如果有选择返回第一个选择的内容,否则返回空字符串
        content_to_return = ""
        if len(response.choices) > 0:
            content_to_return = response.choices[0].message.content

        print(f"[MY_DEBUG] ZhipuAILLMModel._completion is returning: '{content_to_return}'")
        return content_to_return

    @classmethod
    def support_model(cls, model):
        """
        检查是否支持指定的模型
        
        Args:
            model (str): 模型名称
            
        Returns:
            bool: 如果是支持的模型返回True,否则返回False
        """
        # 增加了对常见embedding模型的支持，以便该类能被用于纯embedding场景
        return model in ("glm-4", "glm-4.5-x", "glm-4.5","glm-4.5-air", "glm-4.5-airx", "GLM-4-FlashX-250414", "embedding-2", "text_embedding")  # 当前支持的模型列表，增加了 GLM-4-FlashX-250414

    @classmethod
    def creatable(cls, keys, config):
        """
        检查是否可以创建模型实例
        
        Args:
            keys (dict): 密钥信息
            config (dict): 配置信息
            
        Returns:
            bool: 如果包含必要的API密钥返回True,否则返回False
        """
        return "ZHIPUAI_API_KEY" in keys  # 检查是否包含智谱AI的API密钥

    @classmethod
    def model_style(cls):
        """
        获取模型风格
        
        Returns:
            str: 返回"zhipuai"表示智谱AI风格
        """
        return ModelStyle.ZHIPU_AI

@utils.register_model
class GeminiLLMModel(LLMModel):
    """
    Google Gemini API模型的具体实现类
    通过OpenAI兼容接口调用
    """

    def setup(self, keys, config):
        """
        初始化OpenAI客户端以调用Gemini
        """
        from openai import OpenAI

        # 使用API密钥和指定的base_url初始化客户端
        return OpenAI(api_key=keys["GEMINI_API_KEY"], base_url=self._base_url)

    def _embedding(self, text):
        """
        使用Gemini API生成文本的embedding
        """
        response = self._handle.embeddings.create(
            input=text, model=self._embedding_model
        )
        return response.data[0].embedding

    def _completion(self, prompt, temperature=1):
        """
        使用Gemini API生成文本补全
        """
        messages = [{"role": "user", "content": prompt}]
        response = self._handle.chat.completions.create(
            model=self._model, messages=messages, temperature=temperature
        )
        content_to_return = ""
        if len(response.choices) > 0:
            content_to_return = response.choices[0].message.content
        
        print(f"[MY_DEBUG] GeminiLLMModel._completion is returning: '{content_to_return}'")
        return content_to_return

    @classmethod
    def support_model(cls, model):
        """
        检查是否支持指定的模型
        """
        return "gemini" in model.lower()

    @classmethod
    def creatable(cls, keys, config):
        """
        检查是否可以创建模型实例
        """
        # 说明：Google 的 OpenAI 兼容端点通常为
        #   https://generativelanguage.googleapis.com/v1beta/openai/
        # 该 URL 不包含 "gemini" 字样。旧逻辑强制要求 base_url 含有 "gemini" 会误判不可用。
        # 为兼容现有配置，这里放宽为：只要提供了 GEMINI_API_KEY 即可创建。
        return "GEMINI_API_KEY" in keys and bool(keys["GEMINI_API_KEY"])

    @classmethod
    def model_style(cls):
        """
        获取模型风格
        """
        return ModelStyle.GEMINI

@utils.register_model
class QIANFANLLMModel(LLMModel):
    """
    百度千帆大模型的具体实现类
    支持文心一言等模型的文本生成和embedding生成
    """
    
    def setup(self, keys, config):
        """
        初始化千帆API配置
        将API密钥设置为环境变量
        
        Args:
            keys (dict): 包含API密钥的字典
            config (dict): 配置信息
            
        Returns:
            dict: 包含API密钥的字典
        """
        # 提取需要的密钥
        handle = {k: keys[k] for k in ["QIANFAN_AK", "QIANFAN_SK"]}
        # 设置环境变量
        for k, v in handle.items():
            os.environ[k] = v
        return handle

    def _embedding(self, text):
        """
        使用千帆API生成文本的embedding
        
        Args:
            text (str): 输入文本
            
        Returns:
            list: 文本的embedding向量
        """
        # 获取access token的URL
        url = "https://aip.baidubce.com/oauth/2.0/token?grant_type=client_credentials&client_id={0}&client_secret={1}".format(
            self._handle["QIANFAN_AK"], self._handle["QIANFAN_SK"]
        )
        
        # 发送获取token的请求
        payload = json.dumps("")
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        response = requests.request("POST", url, headers=headers, data=payload)
        
        # 构造embedding API的URL
        url = (
            "https://aip.baidubce.com/rpc/2.0/ai_custom/v1/wenxinworkshop/embeddings/embedding-v1?access_token="
            + str(response.json().get("access_token"))
        )
        
        # 准备输入数据
        input = []
        input.append(text)
        payload = json.dumps({"input": input}, ensure_ascii=False)
        headers = {"Content-Type": "application/json"}
        
        # 发送embedding请求
        response = requests.request("POST", url, headers=headers, data=payload)
        response = json.loads(response.text)
        
        # 返回embedding结果
        return response["data"][0]["embedding"]

    def _completion(self, prompt, temperature=0.00001):
        """
        使用千帆API生成文本补全
        
        Args:
            prompt (str): 输入提示文本
            temperature (float): 采样温度,控制输出的随机性,默认接近0表示确定性输出
            
        Returns:
            str: 生成的文本
        """
        import qianfan  # 导入千帆SDK

        # 构造消息格式
        messages = [{"role": "user", "content": prompt}]
        # 调用千帆chat completion API
        resp = qianfan.ChatCompletion().do(
            messages=messages,         # 传入消息列表
            model=self._model,        # 使用指定的模型
            temperature=temperature    # 设置采样温度
        )
        # 返回生成结果
        content_to_return = resp["result"]

        print(f"[MY_DEBUG] QIANFANLLMModel._completion is returning: '{content_to_return}'")
        return content_to_return

    @classmethod
    def support_model(cls, model):
        """
        检查是否支持指定的模型
        
        Args:
            model (str): 模型名称
            
        Returns:
            bool: 如果是支持的模型返回True,否则返回False
        """
        return model in ("ERNIE-Bot", "Yi-34B-Chat")  # 当前支持的模型列表

    @classmethod
    def creatable(cls, keys, config):
        """
        检查是否可以创建模型实例
        
        Args:
            keys (dict): 密钥信息
            config (dict): 配置信息
            
        Returns:
            bool: 如果包含必要的API密钥返回True,否则返回False
        """
        # 检查是否包含千帆API的必要密钥
        return "QIANFAN_AK" in keys and "QIANFAN_SK" in keys

    @classmethod
    def model_style(cls):
        """
        获取模型风格
        
        Returns:
            str: 返回"qianfan"表示千帆AI风格
        """
        return ModelStyle.QIANFAN

@utils.register_model
class SparkAILLMModel(LLMModel):
    """
    讯飞星火大模型的具体实现类
    支持v1.5、v2.0、v3.0、v3.5等版本的文本生成
    使用WebSocket连接进行实时对话
    """
    
    def setup(self, keys, config):
        """
        初始化星火大模型配置
        根据模型版本设置不同的域名和URL
        
        Args:
            keys (dict): 包含API密钥的字典
            config (dict): 配置信息
            
        Returns:
            dict: 包含参数和密钥的配置字典
        """
        # WebSocket URL模板
        spark_url_tpl = "wss://spark-api.xf-yun.com/{}/chat"
        handle = {"params": {}, "keys": {}}
        
        # 根据模型版本配置参数
        if self._model == "spark_v1.5":
            handle["params"] = {
                "domain": "general",                    # v1.5版本的域名
                "spark_url": spark_url_tpl.format("v1.1"),  # v1.5版本的URL
            }
        elif self._model == "spark_v2.0":
            handle["params"] = {
                "domain": "generalv2",                  # v2.0版本的域名
                "spark_url": spark_url_tpl.format("v2.1"),  # v2.0版本的URL
            }
        elif self._model == "spark_v3.0":
            handle["params"] = {
                "domain": "generalv3",                  # v3.0版本的域名
                "spark_url": spark_url_tpl.format("v3.1"),  # v3.0版本的URL
            }
        elif self._model == "spark_v3.5":
            handle["params"] = {
                "domain": "generalv3.5",                # v3.5版本的域名
                "spark_url": spark_url_tpl.format("v3.5"),  # v3.5版本的URL
            }
            
        # 提取必要的API密钥
        needed_keys = ["SPARK_APPID", "SPARK_API_SECRET", "SPARK_API_KEY"]
        handle["keys"] = {k: keys[k] for k in needed_keys}
        return handle

    def _completion(self, prompt, temperature=0.00001, streaming=False):
        """
        使用星火API生成文本补全
        
        Args:
            prompt (str): 输入提示文本
            temperature (float): 采样温度,默认接近0表示确定性输出
            streaming (bool): 是否使用流式输出,默认False
            
        Returns:
            str: 生成的文本
        """
        # 导入星火SDK
        from sparkai.llm.llm import ChatSparkLLM
        from sparkai.core.messages import ChatMessage

        # 创建星火LLM实例
        spark_llm = ChatSparkLLM(
            spark_api_url=self._handle["params"]["spark_url"],        # API URL
            spark_app_id=self._handle["keys"]["SPARK_APPID"],         # 应用ID
            spark_api_key=self._handle["keys"]["SPARK_API_KEY"],      # API密钥
            spark_api_secret=self._handle["keys"]["SPARK_API_SECRET"], # API密钥
            spark_llm_domain=self._handle["params"]["domain"],        # 模型域名
            temperature=temperature,                                   # 采样温度
            streaming=streaming,                                       # 是否流式输出
        )
        
        # 构造消息格式
        messages = [ChatMessage(role="user", content=prompt)]
        # 生成响应
        resp = spark_llm.generate([messages])
        content_to_return = ""
        if streaming:
            for chunk in resp:
                content_to_return += chunk.text
        else:
            content_to_return = resp[0].text

        print(f"[MY_DEBUG] SparkAILLMModel._completion is returning: '{content_to_return}'")
        return content_to_return

    @classmethod
    def support_model(cls, model):
        """
        检查是否支持指定的模型
        
        Args:
            model (str): 模型名称
            
        Returns:
            bool: 如果是支持的模型返回True,否则返回False
        """
        # 支持的星火模型版本列表
        return model in ("spark_v1.5", "spark_v2.1", "spark_v3.1", "spark_v3.5")

    @classmethod
    def creatable(cls, keys, config):
        """
        检查是否可以创建模型实例
        
        Args:
            keys (dict): 密钥信息
            config (dict): 配置信息
            
        Returns:
            bool: 如果包含所有必要的API密钥返回True,否则返回False
        """
        # 检查是否包含所有必要的星火API密钥
        needed_keys = ["SPARK_APPID", "SPARK_API_SECRET", "SPARK_API_KEY"]
        return all(k in keys for k in needed_keys)

    @classmethod
    def model_style(cls):
        """
        获取模型风格
        
        Returns:
            str: 返回"sparkai"表示星火AI风格
        """
        return ModelStyle.SPARK_AI

def create_llm_model(base_url, model, embedding_model, keys, config=None):
    """
    创建LLM模型实例的工厂函数
    根据模型名称和配置创建对应的模型实例
    
    Args:
        base_url (str): API基础URL
        model (str): 模型名称
        embedding_model (str): 用于生成embedding的模型名称
        keys (dict): API密钥信息
        config (dict, optional): 额外配置信息
        
    Returns:
        LLMModel: 创建的模型实例,如果无法创建则返回None
    """
    # 遍历所有注册的LLM模型类
    for _, model_cls in utils.get_registered_model(ModelType.LLM).items():
        # 检查是否支持该模型且可以创建实例
        if model_cls.support_model(model) and model_cls.creatable(keys, config):
            # 创建并返回模型实例
            return model_cls(base_url, model, embedding_model, keys, config=config)
    return None  # 如果没有找到合适的模型类则返回None


def parse_llm_output(response, patterns, mode="match_last", ignore_empty=False):
    """
    解析LLM的输出文本
    支持使用正则表达式匹配和提取内容
    
    Args:
        response (str): LLM的原始响应文本
        patterns (str or list): 用于匹配的正则表达式模式
        mode (str): 匹配模式,可选值:
            - "match_first": 返回第一个匹配结果
            - "match_last": 返回最后一个匹配结果
            - "match_all": 返回所有匹配结果
        ignore_empty (bool): 是否忽略空匹配结果
        
    Returns:
        根据mode返回匹配的结果:
        - match_first/match_last: 返回单个匹配结果
        - match_all: 返回匹配结果列表
        
    Raises:
        AssertionError: 当ignore_empty为False且没有匹配结果时抛出
    """
    # 如果patterns是字符串,转换为列表
    if isinstance(patterns, str):
        patterns = [patterns]
        
    rets = []  # 存储所有匹配结果
    
    # 按行处理响应文本
    for line in response.split("\n"):
        # 移除markdown加粗标记并去除首尾空白
        line = line.replace("**", "").strip()
        
        # 尝试每个模式进行匹配
        for pattern in patterns:
            if pattern:  # 如果有正则表达式模式
                matchs = re.findall(pattern, line)  # 使用正则表达式查找所有匹配
            else:  # 如果没有模式,使用整行
                matchs = [line]
                
            # 如果找到匹配结果
            if len(matchs) >= 1:
                rets.append(matchs[0])  # 添加第一个匹配结果
                break  # 找到匹配后跳出pattern循环
                
    # 如果不忽略空结果且没有找到匹配
    if not ignore_empty:
        assert rets, "Failed to match llm output"
        
    # 根据不同的模式返回结果
    if mode == "match_first":
        return rets[0]  # 返回第一个匹配
    if mode == "match_last":
        return rets[-1]  # 返回最后一个匹配
    if mode == "match_all":
        return rets  # 返回所有匹配
    return None  # 如果mode不是已知值则返回None
