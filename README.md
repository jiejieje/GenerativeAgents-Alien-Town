## 🛸 GenerativeAgents: Alien Town 外星小镇

![主宣传画面](github页面图片/主宣传画面.gif)

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


### 📺 项目演示

**简介视频：**

https://github.com/user-attachments/assets/your-video-file-id

> 💡 提示：如果视频无法显示，请直接查看仓库中的 `github页面图片/《A外星小镇》简介.mp4` 文件


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

#### 方式1：可视化启动器（非常推荐）
```bash
python AI小镇启动器.py
```
- 打开图形界面，点击选择或创建角色
- 设置模拟步数（建议先试试50步）
- 点击"开始模拟"，实时观看角色们的生活！

📖 **详细使用教程**：想要更详细的操作指导？查看 [《AI外星小镇使用教程》](github页面图片视频等/AI外星小镇使用教程.pdf)（约3分钟即可学会）

#### 方式2：下载预编译版本（推荐给想体验一下的小白用户）
在GitHub页面右侧的 **Releases** 区域下载最新的打包文件：
- 下载后解压到任意目录
- 双击运行 `AI小镇启动器.exe`
- 无需安装Python环境，开箱即用！

⚠️ **重要提示：** 
打包版本使用的是开发者个人的API密钥，目前账号还有余额供大家免费体验。如果运行时没有看到AI角色生成图片和音乐，说明余额已耗尽，此时需要你配置自己的API密钥才能继续使用。


#### 方式3：命令行启动（不太推荐）
```bash
# 激活虚拟环境（如果使用conda）
conda activate myenv

# 创建新的模拟（示例：60步，每步30分钟间隔）
python start.py --name your_simulation_name --start "20240213-09:30" --step 60 --stride 30

# 继续之前的模拟（示例：继续150步）  
python start.py --name your_simulation_name --start "20240213-09:30" --step 150 --stride 10 --resume

# 压缩模拟结果
python compress.py --name your_simulation_name

# 启动回放服务器
python replay.py
```

**回放网页地址示例：**
- 基础回放：`http://127.0.0.1:5000/?name=your_simulation_name`
- 带参数回放：`http://127.0.0.1:5000/?name=your_simulation_name&step=1&speed=1&zoom=0.1`






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

### 🗺️ 地图自定义
想要修改小镇地图？请参考作者的另一个开源项目：
**[Tiled地图转Maze工具](https://github.com/jiejieje/tiled_to_maze.json)** - 支持将Tiled编辑器制作的地图转换为本项目可用的格式



### 📄 许可证
- 项目代码遵循仓库License声明


### 🙏 致谢
特别感谢以下开源项目和贡献者：

- **[x-glacier/GenerativeAgentsCN](https://github.com/x-glacier/GenerativeAgentsCN)** - 非常感谢 x-glacier 大佬提供的中文化框架和建设性建议。没有您精心构建的基础架构，这个外星小镇项目根本不可能实现。向您的技术实力和无私分享精神致以最崇高的敬意！
- **[Stanford Generative Agents](https://github.com/joonspk-research/generative_agents)** - 提供了理论基础和核心思想
- **[Pixi.js](https://github.com/pixijs/pixijs)** - 高效的网页引擎让高清分辨率地图展示成为可能
- **各大AI服务商** - 智谱AI、Google Gemini、Suno、LibLibAI等提供强大的API支持
- **LlamaIndex生态** - 提供了完整的AI工具链支持



---

### 💌 作者的话
作为一名美术专业出身的独立开发者，我深知自己在编程技术上还有很多不足之处。这个项目更多是出于对AI和创意结合的热情而诞生的实验性作品。

如果您在使用过程中发现任何bug、代码问题或有改进建议，非常欢迎通过Issue与我交流指正。每一个反馈都是我学习进步的宝贵机会！

同时也希望这个小镇能给大家带来一些乐趣，或是在游戏开发中提供一些灵感。

⭐ 如果你觉得这个项目有趣，欢迎给个Star支持！  
💬 有问题或建议欢迎提Issue一起讨论  
🤝 也欢迎志同道合的朋友一起参与开发，让AI小镇变得更加精彩  
🎨 特别欢迎美术、音乐、游戏设计等创意领域的朋友加入



