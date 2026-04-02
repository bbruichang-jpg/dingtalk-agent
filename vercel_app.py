"""
钉钉智能体 - 企业内部机器人版本
支持接收群消息并自动回复
"""
from flask import Flask, request, jsonify
import os
import json
import requests
import base64
import hashlib
import time
import hmac
import xml.etree.ElementTree as ET

app = Flask(__name__)

# 钉钉配置
DINGTALK_APP_KEY = os.getenv("DINGTALK_APP_KEY", "")
DINGTALK_APP_SECRET = os.getenv("DINGTALK_APP_SECRET", "")
DINGTALK_TOKEN = os.getenv("DINGTALK_TOKEN", "")
DINGTACK_AES_KEY = os.getenv("DINGTACK_AES_KEY", "")


class DingTalkCrypto:
    """钉钉消息加解密工具"""

    def __init__(self, token, aes_key):
        self.token = token
        self.aes_key = aes_key + "=" * ((8 - len(aes_key) % 8) % 8)
        self.aes_key = base64.b64decode(self.aes_key)

    def decrypt_msg(self, encrypt, msg_signature, timestamp, nonce):
        """解密消息"""
        # 验证签名
        sign = self._signature(timestamp, nonce, encrypt)
        if sign != msg_signature:
            raise Exception("签名验证失败")

        # 解密
        cipher = base64.b64decode(encrypt)
        from Crypto.Cipher import AES
        cryptor = AES.new(self.aes_key, AES.MODE_CBC, self.aes_key[:16])
        plain_text = cryptor.decrypt(cipher)

        # 去除补位
        pad = plain_text[-1]
        if isinstance(pad, str):
            pad = ord(pad)
        content = plain_text[16:-pad]

        # 解析XML
        xml_tree = ET.fromstring(content.decode('utf-8'))
        return xml_tree.find('Content').text

    def encrypt_msg(self, msg, nonce):
        """加密消息"""
        timestamp = str(int(time.time()))
        from Crypto.Cipher import AES
        from Crypto.Util.Padding import pad

        # 添加随机字符串
        text = msg if isinstance(msg, bytes) else msg.encode('utf-8')
        random_str = os.urandom(16)

        # 添加长度
        msg_len = bytes(hex(len(text))[2:].rjust(4, '0'), 'utf-8')

        # 拼接
        content = random_str + msg_len + text
        content = pad(content, 16)

        # 加密
        cryptor = AES.new(self.aes_key, AES.MODE_CBC, self.aes_key[:16])
        encrypt = base64.b64encode(cryptor.encrypt(content)).decode('utf-8')

        # 计算签名
        sign = self._signature(timestamp, nonce, encrypt)

        # 构造XML
        xml = f"""
        <xml>
            <Encrypt><![CDATA[{encrypt}]]></Encrypt>
            <MsgSignature><![CDATA[{sign}]]></MsgSignature>
            <TimeStamp>{timestamp}</TimeStamp>
            <Nonce><![CDATA[{nonce}]]></Nonce>
        </xml>
        """
        return xml

    def _signature(self, timestamp, nonce, encrypt):
        """生成签名"""
        arr = [self.token, timestamp, nonce, encrypt]
        arr.sort()
        sha = hashlib.sha1()
        for item in arr:
            sha.update(item.encode('utf-8'))
        return sha.hexdigest()


def get_access_token():
    """获取钉钉access_token"""
    if not DINGTALK_APP_KEY or not DINGTALK_APP_SECRET:
        return None

    url = "https://api.dingtalk.com/v1.0/oauth2/accessToken"
    data = {
        "appKey": DINGTALK_APP_KEY,
        "appSecret": DINGTALK_APP_SECRET
    }

    try:
        response = requests.post(url, json=data, timeout=10)
        result = response.json()
        if result.get("accessToken"):
            return result["accessToken"]
    except Exception as e:
        print(f"获取access_token失败: {e}")
    return None


def send_group_message(conversation_id, text):
    """发送消息到钉钉群"""
    access_token = get_access_token()
    if not access_token:
        print("错误：无法获取access_token")
        return False

    url = f"https://api.dingtalk.com/v1.0/robot/groupMessages/send?access_token={access_token}"
    data = {
        "msgParam": {
            "content": text
        },
        "msgKey": "sampleText",
        "openConversationId": conversation_id
    }

    try:
        response = requests.post(url, json=data, timeout=10)
        result = response.json()
        print(f"发送消息结果: {result}")
        return True
    except Exception as e:
        print(f"发送消息失败: {e}")
        return False


def process_message(text):
    """处理用户消息，生成回复"""
    # 这里可以调用Agent、LLM等
    # 暂时返回简单回复

    if "分析" in text:
        return "🤖 正在分析中，请稍候...\n\n📝 这是一个示例回复。\n\n你可以修改代码来集成你的智能体。"
    elif "你好" in text:
        return "👋 你好！我是钉钉智能体助手，很高兴为你服务！"
    elif "帮助" in text:
        return "📝 使用方法：\n- 分析中秋节月饼\n- 生成产品文案\n- 你好\n\n更多功能正在开发中..."
    elif "中秋" in text or "月饼" in text:
        return "🥮 中秋节快到了！月饼是中秋的传统美食，寓意团圆美满。\n\n你想要分析什么类型的月饼呢？"
    else:
        return f"🤔 我收到了你的消息：{text}\n\n但我还没学会如何回复这个，试试说'分析'、'你好'或'帮助'吧！"


@app.route('/dingtalk/receive', methods=['POST'])
def dingtalk_receive():
    """接收钉钉企业内部机器人的消息"""
    try:
        # 获取参数
        msg_signature = request.args.get('signature')
        timestamp = request.args.get('timestamp')
        nonce = request.args.get('nonce')

        # 解析消息体
        data = request.get_json()

        if not data or 'encrypt' not in data:
            print("错误：未找到加密消息")
            return jsonify({"errcode": 1, "errmsg": "Invalid request"}), 400

        encrypt = data.get('encrypt')

        # 解密消息
        if not DINGTALK_TOKEN or not DINGTACK_AES_KEY:
            print("错误：未配置TOKEN或AES_KEY")
            return jsonify({"errcode": 1, "errmsg": "Config error"}), 500

        crypto = DingTalkCrypto(DINGTALK_TOKEN, DINGTACK_AES_KEY)
        msg = crypto.decrypt_msg(encrypt, msg_signature, timestamp, nonce)

        print(f"解密后的消息: {msg}")

        # 解析消息内容
        msg_data = json.loads(msg)
        msg_type = msg_data.get('msgtype')
        chat_type = msg_data.get('chatType')
        content = msg_data.get('content', {})
        conversation_id = msg_data.get('conversationId')

        print(f"消息类型: {msg_type}, 聊天类型: {chat_type}")

        # 处理文本消息
        if msg_type == 'text' and chat_type == 'group':
            text_content = content.get('content', {}).get('text', '')

            print(f"用户消息: {text_content}")
            print(f"会话ID: {conversation_id}")

            if not text_content:
                return jsonify({"errcode": 0, "errmsg": "ok"})

            # 处理消息
            reply = process_message(text_content)
            print(f"回复消息: {reply}")

            # 发送回复
            if conversation_id:
                send_group_message(conversation_id, reply)

        return jsonify({"errcode": 0, "errmsg": "ok"})

    except Exception as e:
        print(f"处理异常: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"errcode": 1, "errmsg": str(e)}), 500


@app.route('/dingtalk/webhook', methods=['POST'])
def dingtalk_webhook():
    """自定义机器人Webhook（兼容旧版）"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "message": "Invalid request"}), 400

        print(f"收到钉钉消息: {json.dumps(data, ensure_ascii=False)}")

        if data.get('msgtype') == 'text':
            text_content = data.get('text', {}).get('content', '')
            if '@' in text_content:
                user_message = text_content.split('@')[-1].strip()
            else:
                user_message = text_content.strip()

            print(f"用户消息: {user_message}")
            reply = process_message(user_message)
            send_to_dingtalk(f"📝 {reply}")

        return jsonify({"success": True, "message": "OK"})

    except Exception as e:
        print(f"处理异常: {e}")
        return jsonify({"success": False, "message": str(e)}), 500


def send_to_dingtalk(text):
    """发送消息到钉钉自定义机器人"""
    webhook = os.getenv("DINGTALK_WEBHOOK", "")
    if not webhook:
        print("错误：未配置DINGTALK_WEBHOOK")
        return False

    data = {
        "msgtype": "text",
        "text": {
            "content": text
        }
    }

    try:
        response = requests.post(webhook, json=data, timeout=10)
        result = response.json()
        return result.get("errcode") == 0
    except Exception as e:
        print(f"发送失败: {e}")
        return False


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
        "service": "钉钉智能体（企业内部机器人版本）",
        "status": "running",
        "endpoints": {
            "receive": "/dingtalk/receive",  # 企业内部机器人接收地址
            "webhook": "/dingtalk/webhook",  # 自定义机器人地址
            "chat": "/api/chat"
        },
        "config": {
            "APP_KEY": "✓" if DINGTALK_APP_KEY else "✗",
            "APP_SECRET": "✓" if DINGTALK_APP_SECRET else "✗",
            "TOKEN": "✓" if DINGTALK_TOKEN else "✗",
            "AES_KEY": "✓" if DINGTACK_AES_KEY else "✗"
        }
    })


@app.route('/health', methods=['GET'])
def health():
    """健康检查"""
    return jsonify({"status": "ok"})


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=False)
