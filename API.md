# BiliDownReborn API 文档

## 基础信息

- 基础URL: `https://bilidown.codetea.top`
- 所有请求和响应均使用 JSON 格式
- 所有时间戳使用 ISO 8601 格式
- 所有文件大小以字节为单位

## 认证

### 管理员认证

管理员接口需要先登录获取 session：

```http
POST /admin/login
Content-Type: application/x-www-form-urlencoded

password=your_password
```

响应：
```json
{
    "success": true
}
```

## API 端点

### 1. 视频下载

#### 单个视频下载
```http
POST /download
Content-Type: application/json

{
    "bvid": "BV1xx411c7mD",
    "format": "mp4"  // 可选，默认为 mp4
}
```

响应：
- 成功：返回视频文件
- 失败：
```json
{
    "success": false,
    "message": "错误信息"
}
```

#### 批量视频下载
```http
POST /download/batch
Content-Type: application/json

{
    "bvid": "BV1xx411c7mD",
    "pages": [1, 2, 3],  // 要下载的分P列表
    "task_id": "uuid"    // 任务ID，用于跟踪进度
}
```

响应：
```json
{
    "success": true,
    "message": "下载完成"
}
```

#### 获取下载进度
```http
GET /download/progress/{task_id}
```

响应：
```json
{
    "total": 3,          // 总视频数
    "current": 1,        // 当前下载数
    "status": "downloading"  // 状态：preparing/downloading/completed/error
}
```

#### 获取批量下载文件
```http
GET /download/batch/{task_id}
```

响应：
- 成功：返回 ZIP 文件
- 失败：
```json
{
    "success": false,
    "message": "文件不存在"
}
```

### 2. 用户反馈

#### 提交反馈
```http
POST /feedback
Content-Type: multipart/form-data

email=user@example.com
content=反馈内容
images=图片文件（可选，可多张）
```

响应：
```json
{
    "success": true
}
```

### 3. 管理员接口

#### 获取 IP 状态
```http
GET /admin/ips
```

响应：
```json
{
    "requests": {
        "192.168.1.1": 5
    },
    "bans": {
        "192.168.1.1": "2024-01-01 12:00:00"
    },
    "violations": {
        "192.168.1.1": 2
    }
}
```

#### 封禁 IP
```http
POST /admin/ban/{ip}
Content-Type: application/json

{
    "duration": 3600  // 封禁时长（秒）
}
```

响应：
```json
{
    "success": true
}
```

#### 解封 IP
```http
POST /admin/unban/{ip}
```

响应：
```json
{
    "success": true
}
```

#### 获取临时文件信息
```http
GET /admin/temp/info
```

响应：
```json
{
    "success": true,
    "count": 10,
    "size": 1073741824
}
```

#### 清理临时文件
```http
POST /admin/cleanup/temp
```

响应：
```json
{
    "success": true,
    "message": "清理完成",
    "deleted_count": 10
}
```

#### 获取配置
```http
GET /admin/config
```

响应：
```json
{
    "ip_management": {
        "request_limit": 60,
        "ban_duration": 3600,
        "ban_threshold": 5
    },
    "storage": {
        "max_size": 1073741824
    }
}
```

#### 更新配置
```http
POST /admin/config
Content-Type: application/json

{
    "ip_management": {
        "request_limit": 60,
        "ban_duration": 3600,
        "ban_threshold": 5
    },
    "storage": {
        "max_size": 1073741824
    }
}
```

响应：
```json
{
    "success": true
}
```

## 错误码说明

- 200: 请求成功
- 400: 请求参数错误
- 403: 权限不足
- 404: 资源不存在
- 429: 请求过于频繁
- 500: 服务器内部错误

## 限制说明

1. IP 请求限制：
   - 每分钟最多 60 次请求
   - 超过限制会被临时封禁
   - 轮询请求不计入限制

2. 文件大小限制：
   - 单个视频文件最大 1GB
   - 批量下载总大小最大 1GB

3. 反馈限制：
   - 每次最多上传 5 张图片
   - 每张图片最大 5MB

## 最佳实践

1. 下载视频：
   - 建议使用批量下载接口
   - 使用 task_id 跟踪下载进度
   - 定期检查下载状态

2. 管理 IP：
   - 定期检查 IP 状态
   - 及时清理临时文件
   - 合理设置封禁时长

3. 错误处理：
   - 实现请求重试机制
   - 处理网络超时
   - 验证响应状态

## 示例代码

### Python
```python
import requests

# 下载视频
def download_video(bvid):
    response = requests.post('https://bilidown.codetea.top/download', 
        json={'bvid': bvid})
    if response.status_code == 200:
        with open(f'{bvid}.mp4', 'wb') as f:
            f.write(response.content)

# 批量下载
def batch_download(bvid, pages):
    task_id = str(uuid.uuid4())
    response = requests.post('https://bilidown.codetea.top/download/batch',
        json={'bvid': bvid, 'pages': pages, 'task_id': task_id})
    return task_id

# 检查进度
def check_progress(task_id):
    response = requests.get(f'https://bilidown.codetea.top/download/progress/{task_id}')
    return response.json()
```

### JavaScript
```javascript
// 下载视频
async function downloadVideo(bvid) {
    const response = await fetch('https://bilidown.codetea.top/download', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({bvid})
    });
    if (response.ok) {
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `${bvid}.mp4`;
        a.click();
    }
}

// 批量下载
async function batchDownload(bvid, pages) {
    const taskId = crypto.randomUUID();
    const response = await fetch('https://bilidown.codetea.top/download/batch', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({bvid, pages, task_id: taskId})
    });
    return taskId;
}

// 检查进度
async function checkProgress(taskId) {
    const response = await fetch(`https://bilidown.codetea.top/download/progress/${taskId}`);
    return response.json();
}
```

## 更新日志

### v2.0.0 (2025-05-09)
- 重置版本发布
- 支持单个视频下载
- 支持批量视频下载
- 支持用户反馈
- 支持 IP 管理
- 支持临时文件管理

## 联系方式

如有问题，请通过以下方式联系：

- 提交 Issue
- 发送邮件到：admin@1427.tech