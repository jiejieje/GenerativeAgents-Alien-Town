# 导入必要的库
import http.client
import json
import requests
import os
import sys
import time
from datetime import datetime
import logging

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def check_task_status(task_id, headers):
    """
    检查任务状态
    
    Args:
        task_id: 任务ID
        headers: 请求头
    Returns:
        dict: 任务状态响应
    """
    conn = http.client.HTTPSConnection("midjourncy.com")
    try:
        conn.request("GET", f"/mj/task/{task_id}/fetch", headers=headers)
        res = conn.getresponse()
        return json.loads(res.read().decode("utf-8"))
    finally:
        conn.close()

# 创建保存目录
save_dir = "generated_images"
os.makedirs(save_dir, exist_ok=True)

# 设置请求头
headers = {
   'Authorization': 'Bearer sk-6jS7aOIneMuHdET0ImPQYr0tqVt2E6pdlD4iBIKHDPA23CoE',
   'Content-Type': 'application/json'
}

# 读取JSON文件
json_filename = "wxr31"  # 从文件名中提取，这里先写死，后面可以改成动态获取
try:
    with open(f"results/paint-records/{json_filename}.json", "r", encoding="utf-8") as f:
        paint_records = json.load(f)
except FileNotFoundError:
    logging.error(f"找不到 results/paint-records/{json_filename}.json 文件")
    sys.exit(1)
except json.JSONDecodeError:
    logging.error(f"results/paint-records/{json_filename}.json 文件格式错误")
    sys.exit(1)

# 遍历绘画记录
for record in paint_records:
    timestamp = record.get("时间")
    prompt = record.get("绘画内容")
    agent_name = record.get("智能体")
    if not timestamp or not prompt or not agent_name:
        logging.warning(f"跳过记录，缺少时间戳、绘画内容或智能体名称: {record}")
        continue
    
    logging.info(f"开始处理时间戳为 {timestamp}，智能体为 {agent_name} 的绘画内容")
    
    # 创建智能体文件夹
    agent_dir = os.path.join(save_dir, json_filename, agent_name)
    os.makedirs(agent_dir, exist_ok=True)
    
    # 创建HTTPS连接
    conn = http.client.HTTPSConnection("midjourncy.com")
    
    # 准备请求数据
    payload = json.dumps({
       "prompt": prompt,
       "num_images": 1,  # 设置生成1张图片
       "aspect_ratio": "1:1",  # 设置图片比例为正方形
       "quality": "standard",  # 设置图片质量
       "style": "750",  # 设置图片风格
       "notifyHook": None  # 可选的回调URL
    })
    
    try:
        # 发送POST请求
        conn.request("POST", "/mj/submit/imagine", payload, headers)
        
        # 获取响应
        res = conn.getresponse()
        data = res.read()
        response = json.loads(data.decode("utf-8"))
        
        logging.info(f"API响应: {response}")
        
        # 如果成功提交任务
        if response.get("code") == 1 and "result" in response:
            task_id = response["result"]
            logging.info(f"任务ID: {task_id}, 开始等待生成结果...")
            
            # 轮询检查任务状态
            max_attempts = 100  # 最大尝试次数
            for attempt in range(max_attempts):
                time.sleep(10)  # 每10秒检查一次
                
                status_response = check_task_status(task_id, headers)
                logging.info(f"第{attempt + 1}次检查状态: {status_response}")
                
                # 如果任务完成且有图片URL
                if status_response.get("status") == "SUCCESS" and "imageUrl" in status_response:
                    try:
                        # 使用完整的URL(包含所有参数)
                        image_url = status_response["imageUrl"]
                        logging.info(f"获取到图片URL: {image_url}")
                        
                        # 生成文件名
                        filename = f"{timestamp.replace(':', '').replace(' ', '_')}.png"
                        filepath = os.path.join(agent_dir, filename)
                        
                        # 添加请求头
                        headers_for_image = {
                            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                        }
                        
                        # 下载图片
                        logging.info("开始下载图片...")
                        img_response = requests.get(image_url, headers=headers_for_image)
                        
                        if img_response.status_code == 200:
                            with open(filepath, 'wb') as f:
                                f.write(img_response.content)
                            logging.info(f"图片已成功保存到: {filepath}")
                            break
                        else:
                            logging.error(f"下载图片失败,状态码: {img_response.status_code}")
                            logging.error(f"响应内容: {img_response.text}")
                    except Exception as e:
                        logging.error(f"保存图片时发生错误: {e}")
                        logging.error(f"错误类型: {type(e)}")
                        logging.error(f"错误详情: {str(e)}")

                # 如果任务失败
                elif status_response.get("status") == "FAILED":
                    logging.error("图片生成失败")
                    break
                    
                # 如果达到最大尝试次数
                elif attempt == max_attempts - 1:
                    logging.warning("等待超时,请稍后手动检查结果")
                
                # 继续等待
                else:
                    logging.info(f"任务仍在进行中,继续等待... (剩余尝试次数: {max_attempts - attempt - 1})")
        else:
            logging.error("提交任务失败")

    except Exception as e:
        logging.error(f"处理时间戳为 {timestamp}，智能体为 {agent_name} 的绘画内容时发生错误: {e}")
        logging.error(f"错误类型: {type(e)}")
        logging.error(f"错误详情: {str(e)}")
    finally:
        # 确保连接被关闭
        conn.close()
