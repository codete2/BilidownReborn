from flask import Flask, request, jsonify, send_file, render_template, session, redirect, url_for
from flask_cors import CORS
import requests
import os
import json
import time
import hashlib
import hmac
import base64
import uuid
from datetime import datetime, timedelta
from collections import defaultdict
import threading
import logging
from functools import wraps
import re
import zipfile
import shutil
from werkzeug.utils import secure_filename
import resend

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

# 配置
class Config:
    def __init__(self):
        self.config_file = 'config.json'
        self.config = self.load_config()
    
    def load_config(self):
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return DEFAULT_CONFIG
        except Exception as e:
            logger.error(f"加载配置文件失败: {str(e)}")
            return DEFAULT_CONFIG
    
    def save_config(self):
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=4, ensure_ascii=False)
            return True
        except Exception as e:
            logger.error(f"保存配置文件失败: {str(e)}")
            return False
    
    def get(self, key, default=None):
        return self.config.get(key, default)
    
    def set(self, key, value):
        self.config[key] = value
        return self.save_config()

# 默认配置
DEFAULT_CONFIG = {
    "secret_key": "your-secret-key-here",
    "admin": {
        "salt": "your-salt-here",
        "password_hash": "your-password-hash-here"
    },
    "ip_management": {
        "request_limit": 60,
        "ban_duration": 3600,
        "ban_threshold": 5
    },
    "storage": {
        "max_size": 1073741824
    },
    "email": {
        "smtp_server": "smtp.example.com",
        "smtp_port": 587,
        "sender_email": "your-email@example.com",
        "sender_password": "your-password-here",
        "admin_email": "admin@example.com"
    }
}

# 初始化配置
config = Config()
app.secret_key = config.get('secret_key')

# IP 管理
ip_requests = defaultdict(list)
ip_bans = {}
ip_violations = defaultdict(int)

def is_temp_file(filename):
    """检查是否是临时下载文件"""
    return filename.startswith('temp_') and filename.endswith('.zip')

def get_temp_info():
    """获取临时文件信息"""
    try:
        temp_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'temp')
        if not os.path.exists(temp_dir):
            return {'count': 0, 'size': 0}
        
        total_size = 0
        count = 0
        for filename in os.listdir(temp_dir):
            if is_temp_file(filename):
                file_path = os.path.join(temp_dir, filename)
                total_size += os.path.getsize(file_path)
                count += 1
        
        return {
            'count': count,
            'size': total_size
        }
    except Exception as e:
        logger.error(f"获取临时文件信息失败: {str(e)}")
        return {'count': 0, 'size': 0}

def cleanup_temp_files():
    """清理临时文件"""
    try:
        temp_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'temp')
        if not os.path.exists(temp_dir):
            return 0
        
        deleted_count = 0
        for filename in os.listdir(temp_dir):
            if is_temp_file(filename):
                file_path = os.path.join(temp_dir, filename)
                try:
                    os.remove(file_path)
                    deleted_count += 1
                except Exception as e:
                    logger.error(f"删除文件失败 {filename}: {str(e)}")
        
        return deleted_count
    except Exception as e:
        logger.error(f"清理临时文件失败: {str(e)}")
        return 0

def ip_management(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        ip = request.remote_addr
        
        # 检查是否是轮询请求
        is_polling = request.path in ['/download/progress/', '/admin/ips']
        if is_polling:
            return f(*args, **kwargs)
        
        # 检查是否被封禁
        if ip in ip_bans:
            ban_time = ip_bans[ip]
            if datetime.now() < ban_time:
                return jsonify({
                    'success': False,
                    'message': f'IP已被封禁，解封时间：{ban_time.strftime("%Y-%m-%d %H:%M:%S")}'
                }), 403
            else:
                del ip_bans[ip]
        
        # 清理过期的请求记录
        current_time = datetime.now()
        ip_requests[ip] = [t for t in ip_requests[ip] if current_time - t < timedelta(minutes=1)]
        
        # 检查请求频率
        if len(ip_requests[ip]) >= config.get('ip_management')['request_limit']:
            ip_violations[ip] += 1
            if ip_violations[ip] >= config.get('ip_management')['ban_threshold']:
                ban_duration = config.get('ip_management')['ban_duration']
                ip_bans[ip] = current_time + timedelta(seconds=ban_duration)
                return jsonify({
                    'success': False,
                    'message': f'请求过于频繁，IP已被封禁{ban_duration}秒'
                }), 403
            return jsonify({
                'success': False,
                'message': '请求过于频繁，请稍后再试'
            }), 429
        
        # 记录请求
        ip_requests[ip].append(current_time)
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('admin'):
            return jsonify({'success': False, 'message': '需要管理员权限'}), 403
        return f(*args, **kwargs)
    return decorated_function

def send_thank_you_email(email):
    """发送感谢邮件"""
    try:
        params = {
            "from": "no-reply@example.com",
            "to": [email],
            "subject": "感谢您的反馈 - BiliDownReborn",
            "html": """
            <div style="font-family: 'Microsoft YaHei', Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 0; background-color: #ffffff;">
                <!-- 顶部动态背景 -->
                <div style="background: linear-gradient(45deg, #1296db, #0d7bbf, #1296db); background-size: 200% 200%; animation: gradient 5s ease infinite; padding: 50px 20px; text-align: center; border-radius: 12px 12px 0 0; position: relative; overflow: hidden;">
                    <!-- 动态背景装饰 -->
                    <div style="position: absolute; top: 0; left: 0; right: 0; bottom: 0; background: radial-gradient(circle at 50% 50%, rgba(255,255,255,0.1) 0%, rgba(255,255,255,0) 70%);"></div>
                    <div style="position: absolute; top: 0; left: 0; right: 0; bottom: 0; background: url('data:image/svg+xml,<svg width=\"20\" height=\"20\" viewBox=\"0 0 20 20\" xmlns=\"http://www.w3.org/2000/svg\"><circle cx=\"2\" cy=\"2\" r=\"1\" fill=\"rgba(255,255,255,0.1)\"/></svg>') repeat;"></div>
                    
                    <img src="https://bilidown.codetea.top/assets/bd.png" alt="BiliDownReborn Logo" style="width: 120px; height: auto; margin-bottom: 25px; filter: drop-shadow(0 4px 6px rgba(0,0,0,0.1));">
                    <h1 style="color: white; margin: 0; font-size: 32px; font-weight: 600; text-shadow: 0 2px 4px rgba(0,0,0,0.2); letter-spacing: 1px;">感谢您的反馈！</h1>
                </div>

                <!-- 主要内容 -->
                <div style="padding: 40px 30px; background-color: #ffffff; border-radius: 0 0 12px 12px; box-shadow: 0 8px 24px rgba(0,0,0,0.1);">
                    <!-- 感谢信息卡片 -->
                    <div style="background: linear-gradient(135deg, #f8f9fa 0%, #ffffff 100%); padding: 30px; border-radius: 12px; margin-bottom: 30px; border-left: 4px solid #1296db; box-shadow: 0 4px 12px rgba(0,0,0,0.05);">
                        <p style="color: #333; font-size: 18px; line-height: 1.8; margin-bottom: 20px; font-weight: 500;">亲爱的用户：</p>
                        <p style="color: #333; font-size: 16px; line-height: 1.8; margin-bottom: 20px;">感谢您抽出宝贵的时间为我们提供反馈。您的每一条建议都是我们进步的动力。</p>
                        <p style="color: #333; font-size: 16px; line-height: 1.8; margin-bottom: 20px;">我们会认真对待您的反馈，并持续改进我们的服务，为您提供更好的体验。</p>
                    </div>

                    <!-- 特色功能展示 -->
                    <div style="display: flex; justify-content: space-between; margin: 40px 0; text-align: center;">
                        <div style="flex: 1; padding: 20px; background: linear-gradient(135deg, #f8f9fa 0%, #ffffff 100%); border-radius: 12px; margin: 0 10px; box-shadow: 0 4px 12px rgba(0,0,0,0.05);">
                            <div style="color: #1296db; font-size: 32px; margin-bottom: 15px;">🚀</div>
                            <p style="color: #333; font-size: 16px; font-weight: 500; margin-bottom: 10px;">快速下载</p>
                            <p style="color: #666; font-size: 14px;">极速下载体验</p>
                        </div>
                        <div style="flex: 1; padding: 20px; background: linear-gradient(135deg, #f8f9fa 0%, #ffffff 100%); border-radius: 12px; margin: 0 10px; box-shadow: 0 4px 12px rgba(0,0,0,0.05);">
                            <div style="color: #1296db; font-size: 32px; margin-bottom: 15px;">🎯</div>
                            <p style="color: #333; font-size: 16px; font-weight: 500; margin-bottom: 10px;">批量处理</p>
                            <p style="color: #666; font-size: 14px;">高效批量下载</p>
                        </div>
                        <div style="flex: 1; padding: 20px; background: linear-gradient(135deg, #f8f9fa 0%, #ffffff 100%); border-radius: 12px; margin: 0 10px; box-shadow: 0 4px 12px rgba(0,0,0,0.05);">
                            <div style="color: #1296db; font-size: 32px; margin-bottom: 15px;">🔒</div>
                            <p style="color: #333; font-size: 16px; font-weight: 500; margin-bottom: 10px;">安全可靠</p>
                            <p style="color: #666; font-size: 14px;">安全稳定运行</p>
                        </div>
                    </div>

                    <!-- 行动按钮 -->
                    <div style="text-align: center; margin: 40px 0;">
                        <a href="https://bilidown.codetea.top" style="display: inline-block; background: linear-gradient(45deg, #1296db, #0d7bbf); color: white; padding: 16px 45px; text-decoration: none; border-radius: 30px; font-weight: bold; font-size: 18px; box-shadow: 0 4px 15px rgba(18, 150, 219, 0.3); transition: all 0.3s ease; letter-spacing: 1px;">访问 BiliDownReborn</a>
                    </div>

                    <!-- 分隔线 -->
                    <div style="border-top: 1px solid #eee; margin: 40px 0;"></div>

                    <!-- 底部信息 -->
                    <div style="text-align: center;">
                        <p style="color: #333; font-size: 18px; margin-bottom: 20px; font-weight: 500;">期待您的再次使用！</p>
                        <p style="color: #666; font-size: 16px; margin-bottom: 10px;">BiliDownReborn 团队</p>
                        <p style="color: #999; font-size: 14px;">此邮件由系统自动发送，请勿直接回复</p>
                    </div>
                </div>

                <!-- 页脚 -->
                <div style="text-align: center; padding: 25px; background: linear-gradient(135deg, #f8f9fa 0%, #ffffff 100%); border-radius: 0 0 12px 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.05);">
                    <p style="color: #999; font-size: 12px; margin: 0;">© 2024 BiliDownReborn. All rights reserved.</p>
                </div>
            </div>

            <style>
            @keyframes gradient {
                0% { background-position: 0% 50%; }
                50% { background-position: 100% 50%; }
                100% { background-position: 0% 50%; }
            }
            </style>
            """
        }
        
        email = resend.Emails.send(params)
        return True
    except Exception as e:
        logger.error(f"发送邮件失败: {str(e)}")
        return False

def forward_feedback_to_admin(feedback_data, images):
    """转发反馈给管理员"""
    try:
        # 构建邮件内容
        content = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; background-color: #f8f9fa; border-radius: 8px;">
            <h2 style="color: #333; margin-bottom: 20px;">新的用户反馈</h2>
            
            <div style="background-color: white; padding: 20px; border-radius: 8px; margin-bottom: 20px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                <p style="margin: 0 0 10px 0;"><strong>时间：</strong> {feedback_data['timestamp']}</p>
                <p style="margin: 0 0 10px 0;"><strong>用户邮箱：</strong> {feedback_data['email']}</p>
                <p style="margin: 0 0 10px 0;"><strong>用户IP：</strong> {feedback_data['ip']}</p>
                <p style="margin: 0 0 10px 0;"><strong>反馈内容：</strong></p>
                <div style="background-color: #f8f9fa; padding: 15px; border-radius: 4px; margin-top: 10px;">
                    {feedback_data['content']}
                </div>
            </div>
            
            <div style="background-color: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                <h3 style="color: #333; margin-top: 0;">附件图片</h3>
                <div style="display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 15px;">
                    {''.join(f'<img src="cid:{img}" style="width: 100%; border-radius: 4px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">' for img in images)}
                </div>
            </div>
        </div>
        """
        
        params = {
            "from": "no-reply@example.com",
            "to": ["admin@example.com"],
            "subject": "新的用户反馈",
            "html": content
        }
        
        email = resend.Emails.send(params)
        return True
    except Exception as e:
        logger.error(f"转发反馈失败: {str(e)}")
        return False

# 路由
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/admin')
def admin():
    if not session.get('admin'):
        return redirect(url_for('admin_login'))
    return render_template('admin_panel.html')

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        password = request.form.get('password')
        salt = config.get('admin')['salt']
        password_hash = config.get('admin')['password_hash']
        
        # 验证密码
        if hashlib.sha256((password + salt).encode()).hexdigest() == password_hash:
            session['admin'] = True
            return jsonify({'success': True})
        return jsonify({'success': False, 'message': '密码错误'})
    
    return render_template('admin_login.html')

@app.route('/admin/logout')
def admin_logout():
    session.pop('admin', None)
    return redirect(url_for('admin_login'))

@app.route('/admin/ips')
@admin_required
def get_ip_status():
    return jsonify({
        'requests': {ip: len(requests) for ip, requests in ip_requests.items()},
        'bans': {ip: ban_time.strftime('%Y-%m-%d %H:%M:%S') for ip, ban_time in ip_bans.items()},
        'violations': dict(ip_violations)
    })

@app.route('/admin/ban/<ip>', methods=['POST'])
@admin_required
def ban_ip(ip):
    duration = request.json.get('duration', 3600)
    ip_bans[ip] = datetime.now() + timedelta(seconds=duration)
    return jsonify({'success': True})

@app.route('/admin/unban/<ip>', methods=['POST'])
@admin_required
def unban_ip(ip):
    if ip in ip_bans:
        del ip_bans[ip]
    return jsonify({'success': True})

@app.route('/admin/temp/info')
@admin_required
def get_temp_info_route():
    try:
        info = get_temp_info()
        return jsonify({
            'success': True,
            'count': info['count'],
            'size': info['size']
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

@app.route('/admin/cleanup/temp', methods=['POST'])
@admin_required
def cleanup_temp_files_route():
    try:
        deleted_count = cleanup_temp_files()
        return jsonify({
            'success': True,
            'message': '清理完成',
            'deleted_count': deleted_count
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

@app.route('/admin/config', methods=['GET', 'POST'])
@admin_required
def manage_config():
    if request.method == 'POST':
        try:
            new_config = request.json
            # 更新配置
            for key, value in new_config.items():
                config.set(key, value)
            return jsonify({'success': True})
        except Exception as e:
            return jsonify({'success': False, 'message': str(e)})
    
    # 获取配置
    return jsonify({
        'ip_management': config.get('ip_management'),
        'storage': config.get('storage')
    })

@app.route('/download', methods=['POST'])
@ip_management
def download_video():
    try:
        data = request.get_json()
        bvid = data.get('bvid')
        format = data.get('format', 'mp4')
        
        if not bvid:
            return jsonify({'success': False, 'message': '缺少必要参数'})
        
        # 获取视频信息
        api_url = f'https://api.bilibili.com/x/web-interface/view?bvid={bvid}'
        response = requests.get(api_url)
        video_info = response.json()
        
        if video_info['code'] != 0:
            return jsonify({'success': False, 'message': '获取视频信息失败'})
        
        # 获取下载地址
        download_url = f'https://api.bilibili.com/x/player/playurl?bvid={bvid}&cid={video_info["data"]["cid"]}&qn=80&fnval=16'
        response = requests.get(download_url)
        download_info = response.json()
        
        if download_info['code'] != 0:
            return jsonify({'success': False, 'message': '获取下载地址失败'})
        
        # 下载视频
        video_url = download_info['data']['durl'][0]['url']
        response = requests.get(video_url, stream=True)
        
        # 保存视频
        filename = f'{bvid}.{format}'
        with open(filename, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
        
        return send_file(filename, as_attachment=True)
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/download/batch', methods=['POST'])
@ip_management
def batch_download():
    try:
        data = request.get_json()
        bvid = data.get('bvid')
        pages = data.get('pages', [])
        task_id = data.get('task_id')
        
        if not bvid or not pages or not task_id:
            return jsonify({'success': False, 'message': '缺少必要参数'})
        
        # 创建临时目录
        temp_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'temp')
        os.makedirs(temp_dir, exist_ok=True)
        
        # 创建进度文件
        progress_file = os.path.join(temp_dir, f'progress_{task_id}.json')
        with open(progress_file, 'w') as f:
            json.dump({'total': len(pages), 'current': 0, 'status': 'preparing'}, f)
        
        # 下载视频
        downloaded_files = []
        for i, page in enumerate(pages):
            try:
                # 更新进度
                with open(progress_file, 'w') as f:
                    json.dump({'total': len(pages), 'current': i, 'status': 'downloading'}, f)
                
                # 获取视频信息
                api_url = f'https://api.bilibili.com/x/web-interface/view?bvid={bvid}&p={page}'
                response = requests.get(api_url)
                video_info = response.json()
                
                if video_info['code'] != 0:
                    raise Exception('获取视频信息失败')
                
                # 获取下载地址
                download_url = f'https://api.bilibili.com/x/player/playurl?bvid={bvid}&cid={video_info["data"]["cid"]}&qn=80&fnval=16'
                response = requests.get(download_url)
                download_info = response.json()
                
                if download_info['code'] != 0:
                    raise Exception('获取下载地址失败')
                
                # 下载视频
                video_url = download_info['data']['durl'][0]['url']
                response = requests.get(video_url, stream=True)
                
                # 保存视频
                filename = f'{bvid}_p{page}.mp4'
                filepath = os.path.join(temp_dir, filename)
                with open(filepath, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                
                downloaded_files.append(filepath)
            except Exception as e:
                logger.error(f"下载视频失败: {str(e)}")
                continue
        
        # 创建压缩包
        zip_filename = f'temp_{task_id}.zip'
        zip_path = os.path.join(temp_dir, zip_filename)
        with zipfile.ZipFile(zip_path, 'w') as zipf:
            for file in downloaded_files:
                zipf.write(file, os.path.basename(file))
        
        # 清理临时文件
        for file in downloaded_files:
            try:
                os.remove(file)
            except:
                pass
        
        # 更新进度
        with open(progress_file, 'w') as f:
            json.dump({'total': len(pages), 'current': len(pages), 'status': 'completed'}, f)
        
        return jsonify({'success': True, 'message': '下载完成'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/download/progress/<task_id>')
def get_download_progress(task_id):
    try:
        progress_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'temp', f'progress_{task_id}.json')
        if os.path.exists(progress_file):
            with open(progress_file, 'r') as f:
                progress = json.load(f)
            return jsonify(progress)
        return jsonify({'total': 0, 'current': 0, 'status': 'not_found'})
    except Exception as e:
        return jsonify({'total': 0, 'current': 0, 'status': 'error', 'message': str(e)})

@app.route('/download/batch/<task_id>')
def get_batch_download(task_id):
    try:
        zip_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'temp', f'temp_{task_id}.zip')
        if os.path.exists(zip_path):
            return send_file(zip_path, as_attachment=True)
        return jsonify({'success': False, 'message': '文件不存在'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/feedback', methods=['POST'])
@ip_management
def submit_feedback():
    try:
        data = request.form
        email = data.get('email')
        content = data.get('content')
        images = request.files.getlist('images')
        
        if not email or not content:
            return jsonify({'success': False, 'message': '缺少必要参数'})
        
        # 创建反馈目录
        feedback_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'feedback')
        os.makedirs(feedback_dir, exist_ok=True)
        
        # 保存反馈
        feedback_data = {
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'email': email,
            'content': content,
            'ip': request.remote_addr
        }
        
        feedback_file = os.path.join(feedback_dir, f'feedback_{int(time.time())}.json')
        with open(feedback_file, 'w', encoding='utf-8') as f:
            json.dump(feedback_data, f, ensure_ascii=False, indent=4)
        
        # 保存图片
        image_paths = []
        for image in images:
            if image:
                filename = secure_filename(image.filename)
                image_path = os.path.join(feedback_dir, filename)
                image.save(image_path)
                image_paths.append(image_path)
        
        # 发送感谢邮件
        send_thank_you_email(email)
        
        # 转发反馈给管理员
        forward_feedback_to_admin(feedback_data, image_paths)
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)