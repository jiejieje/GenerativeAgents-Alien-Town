## 🛸 GenerativeAgents: Alien Town 外星小镇

### 🎯 这是什么？
这是一个**智能AI小镇模拟器**！你可以创造虚拟角色，让他们在小镇里自由生活，而且他们会：
- 🎨 **自己画画** - AI角色会根据自己的心情和想法自动创作图片
- 🎵 **自己作曲** - AI角色会根据自己的心情和想法自主创作音乐  
- 💻 **自己编程** - AI角色会根据自己的想法能写出生命游戏的网页代码模拟生命！

### ✨ 项目特色
相比其他AI小镇项目（如斯坦福小镇），我们的AI角色更有创造力：
- 🎨 **智能绘画**：基于 LibLibAI 接口，角色可以根据情感和想法自动生成图片
- 🎵 **音乐创作**：基于 Suno 接口，角色能够创作和分享音乐
- 🎮 **代码生成**：基于 Gemini 接口，角色甚至能编写生命游戏等网页应用
- 🖥️ **可视化界面**：一键启动，实时观察角色们的生活
- 🎮 **PixiJS引擎**：使用高性能的PixiJS渲染引擎，流畅展示角色动画和场景




### 📋 开始使用

#### 🔧 环境要求
- Python 3.9 或更高版本（推荐 3.10/3.11）
- vpn网络连接（用于AI服务调用）

#### 💾 安装步骤
1. 下载或克隆项目到本地
2. 安装依赖包：
```bash
pip install -r requirements.txt
```

#### ⚙️ 配置密钥（重要！）
运行前需要在 `data/config.json` 文件中填入AI服务的密钥：

```json
{
  "agent_base": {
    "associate": {
      "embedding": {
        "type": "zhipuai",
        "model": "embedding-2",
        "api_key": "你的智谱AI密钥（用于向量化）"
      }
    }
  },
  "services": {
    "gemini": { 
      "api_key": "你的Gemini密钥", 
      "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
      "model": "gemini-2.5-flash"
    },
    "suno": { 
      "api_key": "你的Suno音乐API密钥", 
      "base_url": "https://apibox.erweima.ai"
    },
    "liblibai": { 
      "access_key": "你的LibLibAI访问密钥", 
      "secret_key": "你的LibLibAI秘密密钥", 
      "base_url": "https://openapi.liblibai.cloud"
    }
  }
}
```

**💡 小贴士：**
- 智谱AI：用于角色的基础对话和思考，对应网址：https://open.bigmodel.cn/usercenter/proj-mgmt/apikeys
- Gemini：用于代码生成功能，对应网址：https://aistudio.google.com/app/apikey
- Suno：用于音乐创作功能，对应网址：https://sunoapi.org/zh-CN
- LibLibAI：用于图片绘画功能，对应网址：https://www.liblib.art/apis

### 🚀 开始体验

#### 方式1：可视化启动器（推荐新手）
```bash
python AI小镇启动器.py
```
- 打开图形界面，点击选择或创建角色
- 设置模拟步数（建议先试试50步）
- 点击"开始模拟"，实时观看角色们的生活！

#### 方式2：下载预编译版本（推荐小白用户）
在GitHub页面右侧的 **Releases** 区域下载最新的打包文件：
- 下载后解压到任意目录
- 双击运行 `AI小镇启动器.exe`
- 无需安装Python环境，开箱即用！

#### 方式3：命令行启动（适合进阶用户）
```bash
# 创建新的模拟
python start.py --name 你的模拟名称 --step 50

# 继续之前的模拟  
python start.py --name 你的模拟名称 --resume --step 100
```





### 🎭 观看角色作品
模拟运行后，你可以在以下地方找到角色们的创作：
- 📁 `results/`文件夹 - 模拟记录和数据
- 🎨 生成的图片 - 在 `frontend/static/generated_images/`
- 🎵 创作的音乐 - 在 `frontend/static/generated_music/` 
- 💻 编写的代码 - 在 `frontend/static/generated_html_sims/`

### ❓ 常见问题

**Q: 提示缺少 PySide6 怎么办？**
A: 运行 `pip install PySide6` 安装图形界面库

**Q: 运行时说缺少密钥？**  
A: 检查 `data/config.json` 文件，确保填入了正确的API密钥

**Q: 角色不生成图片/音乐/生命游戏代码？**
A: 请按以下步骤检查：
1. 确认对应的API密钥已正确配置，并且账户有足够余额
2. 网络环境要求：
   - 🎵 **音乐/生命游戏代码**：需要开启VPN（推荐香港地区）
   - 🎨 **图片生成**：需要关闭VPN，使用国内网络
3. 由于使用的API服务商来自全球各地，暂时无法在统一网络环境下运行，给您带来不便敬请谅解

**Q: Windows下出现中文乱码？**
A: 一般不影响运行，如果介意可以尝试：
- 确保文件保存为UTF-8编码
- 在终端中运行 `chcp 65001` 设置UTF-8编码

### 🔧 进阶功能
- 📦 **一键打包**：可以通过修改 `ga_multi.spec` 将项目打包成独立程序
- 🎬 **回放系统**：支持通过 `replay.py` 回放和分析模拟过程
- 📊 **数据分析**：可查看角色行为模式、创作统计等详细数据





### 📄 许可证
- 项目代码遵循仓库License声明
- 像素风角色图和贴图等美术素材请遵循原作者版权要求

### 🙏 致谢
- Stanford的Generative Agents论文提供了理论基础
- LlamaIndex生态提供了强大的AI工具链
- 各大AI服务商（智谱、Gemini、Suno、LibLibAI等）提供API支持
- Pixi.js等前端技术让网页展示成为可能

---
⭐ 如果你觉得这个项目有趣，欢迎给个Star支持！
💬 有问题或建议可以提Issue讨论


