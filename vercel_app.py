"""
钉钉智能体 - Vercel部署版本
这是部署到Vercel的简化版，支持手机钉钉使用
"""
from flask import Flask, request, jsonify
import os
import json
import requests

app = Flask(__name__)

# 钉钉配置
DINGTALK_WEBHOOK = os.getenv("DINGTALK_WEBHOOK", "")


def send_to_dingtalk(text):
    """发送消息到钉钉"""
    if not DINGTALK_WEBHOOK:
        print("错误：未配置DINGTALK_WEBHOOK")
        return False

    data = {
        "msgtype": "text",
        "text": {
            "content": text
        }
    }

    try:
        response = requests.post(DINGTALK_WEBHOOK, json=data, timeout=10)
        result = response.json()
        return result.get("errcode") == 0
    except Exception as e:
        print(f"发送失败: {e}")
        return False


def process_message(text):
    """处理用户消息，生成回复"""
    # 这里可以调用Agent、LLM等
    # 暂时返回简单回复

    if "分析" in text:
        return "🤖 正在分析中，请稍候...\n\n📝 这是一个示例回复。\n\n你可以修改代码来集成你的智能体。"
    elif "你好" in text:
        return "👋 你好！我是钉钉智能体助手。"
    elif "帮助" in text:
        return "📝 使用方法：\n- 分析中秋节月饼\n- 生成产品文案\n- 你好"
    else:
        return f"🤔 我收到了你的消息：{text}\n\n但我还没学会如何回复这个，请说'分析'或'你好'试试。"


@app.route('/dingtalk/webhook', methods=['POST'])
def dingtalk_webhook():
    """钉钉机器人Webhook"""
    try:
        # 解析消息
        data = request.get_json()

        if not data:
            return jsonify({"success": False, "message": "Invalid request"}), 400

        # 记录收到的消息
        print(f"收到钉钉消息: {json.dumps(data, ensure_ascii=False)}")

        # 处理文本消息
        if data.get('msgtype') == 'text':
            text_content = data.get('text', {}).get('content', '')

            # 提取@后的内容（移除@机器人部分）
            if '@' in text_content:
                user_message = text_content.split('@')[-1].strip()
            else:
                user_message = text_content.strip()

            print(f"用户消息: {user_message}")

            if not user_message:
                return jsonify({"success": True, "message": "OK"})

            # 处理消息
            reply = process_message(user_message)

            # 发送回复
            send_to_dingtalk(f"📝 {reply}")

        return jsonify({"success": True, "message": "OK"})

    except Exception as e:
        print(f"处理异常: {e}")
        return jsonify({"success": False, "message": str(e)}), 500


@app.route('/api/chat', methods=['POST'])
def chat():
    """聊天API接口"""
    try:
        data = request.get_json()
        message = data.get("message", "")

        if not message:
            return jsonify({"error": "Message is required"}), 400

        reply = process_message(message)

        return jsonify({
            "reply": reply
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/', methods=['GET'])
def home():
    """首页"""
    return jsonify({
        "service": "钉钉智能体",
        "status": "running",
        "endpoints": {
            "webhook": "/dingtalk/webhook",
            "chat": "/api/chat"
        }
    })


@app.route('/health', methods=['GET'])
def health():
    """健康检查"""
    return jsonify({"status": "ok"})


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=False)
