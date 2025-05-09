# BiliDownReborn

一个基于 Flask 的 B 站视频下载工具。

## 功能特点

- 支持单个视频下载
- 支持批量视频下载
- 支持视频格式选择
- 支持下载进度显示
- 支持用户反馈
- 支持 IP 管理
- 支持临时文件管理

## 安装说明

1. 克隆仓库
```bash
git clone https://github.com/yourusername/BiliDownReborn.git
cd BiliDownReborn
```

2. 安装依赖
```bash
pip install -r requirements.txt
```

3. 配置
- 复制 `config.example.json` 为 `config.json`
- 修改 `config.json` 中的配置项

4. 运行
```bash
python app.py
```

## 配置说明

在 `config.json` 中配置以下项目：

- `secret_key`: Flask 应用的密钥
- `admin`: 管理员账户配置
- `ip_management`: IP 管理配置
- `storage`: 存储配置

## 安全说明

- 请确保 `config.json` 不会被提交到版本控制系统
- 请妥善保管管理员密码
- 请定期清理临时文件
- 请及时更新依赖包

## 许可证

GPLv3 LICENSE

## 贡献指南

欢迎提交 Issue 和 Pull Request。

## 联系方式

如有问题，请通过以下方式联系：

- 提交 Issue
- 发送邮件到：admin@1427.tech