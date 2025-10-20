import time
import threading
import json
import re
from typing import Dict, Any, Optional
from django.core.cache import cache
import hashlib
from .models import APIKey, RateLimit, ConversationSession
from django.conf import settings

# 全局配置
# API_KEY_LENGTH = 32
# TOKEN_EXPIRY_SECONDS = 3600
# RATE_LIMIT_MAX = 5  # 每分钟最大请求数
# RATE_LIMIT_INTERVAL = 60

# 线程锁用于速率限制
rate_lock = threading.Lock()

def json_to_markdown(json_response: str) -> str:
    """
    将JSON格式的AI响应转换为Markdown格式，适配前端显示
    """
    try:
        # 清理Markdown代码块标记
        cleaned_response = json_response.strip()
        if cleaned_response.startswith('```json'):
            cleaned_response = cleaned_response[7:]  # 移除 ```json
        if cleaned_response.startswith('```'):
            cleaned_response = cleaned_response[3:]   # 移除 ```
        if cleaned_response.endswith('```'):
            cleaned_response = cleaned_response[:-3]  # 移除结尾的 ```
        
        # 清理HTML标签，提取纯文本
        cleaned_response = re.sub(r'<[^>]+>', '', cleaned_response)
        
        # 尝试解析JSON
        data = json.loads(cleaned_response.strip())
        
        # 构建Markdown格式的分析报告
        markdown_content = "# 🔍 故障分析报告\n\n"
        
        # 故障摘要
        fault_summary = data.get("fault_summary", {})
        markdown_content += "## 📋 故障摘要\n\n"
        markdown_content += f"**严重程度**: {fault_summary.get('severity', 'UNKNOWN')}\n\n"
        markdown_content += f"**故障分类**: {fault_summary.get('category', 'UNKNOWN')}\n\n"
        markdown_content += f"**故障描述**: {fault_summary.get('description', '无描述')}\n\n"
        
        affected_services = fault_summary.get('affected_services', [])
        if affected_services:
            markdown_content += f"**受影响服务**: {', '.join(affected_services)}\n\n"
        
        error_codes = fault_summary.get('error_codes', [])
        if error_codes:
            markdown_content += f"**错误码**: {', '.join(error_codes)}\n\n"
        
        # 根因分析
        root_cause = data.get("root_cause_analysis", {})
        markdown_content += "## 🔍 根因分析\n\n"
        markdown_content += f"**主要原因**: {root_cause.get('primary_cause', '未识别')}\n\n"
        
        contributing_factors = root_cause.get('contributing_factors', [])
        if contributing_factors:
            markdown_content += "**影响因素**:\n"
            for factor in contributing_factors:
                markdown_content += f"- {factor}\n"
            markdown_content += "\n"
        
        markdown_content += f"**置信度**: {root_cause.get('confidence_level', 'UNKNOWN')}\n\n"
        markdown_content += f"**分析推理**: {root_cause.get('reasoning', '无推理过程')}\n\n"
        
        # 解决方案
        solutions = data.get("solutions", {})
        markdown_content += "## 🛠️ 解决方案\n\n"
        
        # 立即行动
        immediate_actions = solutions.get("immediate_actions", [])
        if immediate_actions:
            markdown_content += "### 🚨 立即行动\n\n"
            for action in immediate_actions:
                priority = action.get('priority', 'UNKNOWN')
                priority_emoji = {"HIGH": "🔴", "MEDIUM": "🟡", "LOW": "🟢"}.get(priority, "⚪")
                markdown_content += f"{priority_emoji} **{priority}**: {action.get('action', '无行动')}\n\n"
        
        # 长期修复
        long_term_fixes = solutions.get("long_term_fixes", [])
        if long_term_fixes:
            markdown_content += "### 🔧 长期修复\n\n"
            for fix in long_term_fixes:
                priority = fix.get('priority', 'UNKNOWN')
                priority_emoji = {"HIGH": "🔴", "MEDIUM": "🟡", "LOW": "🟢"}.get(priority, "⚪")
                markdown_content += f"{priority_emoji} **{priority}**: {fix.get('action', '无行动')}\n\n"
        
        # 预防措施
        prevention_measures = solutions.get("prevention_measures", [])
        if prevention_measures:
            markdown_content += "### 🛡️ 预防措施\n\n"
            for measure in prevention_measures:
                priority = measure.get('priority', 'UNKNOWN')
                priority_emoji = {"HIGH": "🔴", "MEDIUM": "🟡", "LOW": "🟢"}.get(priority, "⚪")
                markdown_content += f"{priority_emoji} **{priority}**: {measure.get('action', '无行动')}\n\n"
        
        # 监控建议
        monitoring_recommendations = data.get("monitoring_recommendations", [])
        if monitoring_recommendations:
            markdown_content += "## 📊 监控建议\n\n"
            for i, recommendation in enumerate(monitoring_recommendations, 1):
                markdown_content += f"{i}. {recommendation}\n"
            markdown_content += "\n"
        
        return markdown_content
        
    except json.JSONDecodeError:
        # 如果不是有效的JSON，返回原始响应
        return json_response
    except Exception as e:
        # 其他错误，返回原始响应
        return json_response

def deepseek_r1_api_call(prompt: str) -> str:
    """模拟 DeepSeek-R1 API 调用函数"""
    from topklogsystem import TopKLogSystem
    system = TopKLogSystem(
        log_path="./data/log",
        llm="deepseek-r1:7b",
        embedding_model="bge-large:latest"
    )

    query = prompt
    result = system.query(query)
    time.sleep(0.5)

    # 获取原始JSON响应
    json_response = result["response"]
    print(f"🔍 原始JSON响应长度: {len(json_response)} 字符")
    print(f"🔍 原始响应前200字符: {json_response[:200]}...")
    
    # 转换为Markdown格式
    markdown_response = json_to_markdown(json_response)
    print(f"✅ 转换后Markdown长度: {len(markdown_response)} 字符")
    print(f"✅ 转换后前200字符: {markdown_response[:200]}...")
    
    return markdown_response

def create_api_key(user: str) -> str:
    """创建 API Key 并保存到数据库"""
    key = APIKey.generate_key()
    expiry = time.time() + settings.TOKEN_EXPIRY_SECONDS
    
    api_key = APIKey.objects.create(
        key=key,
        user=user,
        expiry_time=expiry
    )
    
    # 创建对应的速率限制记录
    RateLimit.objects.create(
        api_key=api_key,
        reset_time=time.time() + settings.RATE_LIMIT_INTERVAL
    )
    
    return key

def validate_api_key(key_str: str) -> bool:
    """验证 API Key 是否存在且未过期"""
    try:
        api_key = APIKey.objects.get(key=key_str)
        if api_key.is_valid():
            return True
        else:
            api_key.delete()  # 删除过期key
            return False
    except APIKey.DoesNotExist:
        return False

def check_rate_limit(key_str: str) -> bool:
    """检查 API Key 的请求频率是否超过限制"""
    with rate_lock:
        try:
            # api_key = APIKey.objects.get(key=key_str)
            # rate_limit = RateLimit.objects.get(api_key=api_key)
            rate_limit = RateLimit.objects.select_related('api_key').get(api_key__key=key_str)
            
            current_time = time.time()
            if current_time > rate_limit.reset_time:
                rate_limit.count = 1
                rate_limit.reset_time = current_time + settings.RATE_LIMIT_INTERVAL
                rate_limit.save()
                return True
            elif rate_limit.count < settings.RATE_LIMIT_MAX:
                rate_limit.count += 1
                rate_limit.save()
                return True
            else:
                return False
        except RateLimit.DoesNotExist:
            # 如果速率限制记录不存在，创建一个新的
            try:
                current_time = time.time()
                api_key = APIKey.objects.get(key=key_str)
                RateLimit.objects.create(
                    api_key=api_key,
                    count=1,
                    reset_time=current_time + settings.RATE_LIMIT_INTERVAL
                )
                return True
            except APIKey.DoesNotExist:
                return False

# def get_or_create_session(session_id: str, user: APIKey) -> ConversationSession:
    # """获取或创建会话，关联当前用户（通过API Key）"""
    # session, created = ConversationSession.objects.get_or_create(
        # session_id=session_id,
        # user=user,  # 绑定用户
        # defaults={'context': ''}
    # )
    # return session

def get_or_create_session(session_id: str, user: APIKey) -> ConversationSession:
    """
    获取或创建用户的专属会话：
    - 若用户+session_id已存在 → 加载旧会话（保留历史）
    - 若不存在 → 创建新会话（空历史）
    """
    session, created = ConversationSession.objects.get_or_create(
        session_id=session_id,  # 匹配会话ID
        user=user,              # 匹配当前用户（关键！避免跨用户会话冲突）
        defaults={'context': ''}
    )
    # 调试日志：确认是否创建新会话（created=True 表示新会话）
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"会话 {session_id}（用户：{user.user}）{'创建新会话' if created else '加载旧会话'}")
    return session

def get_cached_reply(prompt: str, session_id: str, user: APIKey) -> str | None:
    """缓存键包含 session_id 和 user，避免跨会话冲突"""
    cache_key = f"reply:{user.user}:{session_id}:{hash(prompt)}"
    return cache.get(cache_key)

def set_cached_reply(prompt: str, reply: str, session_id: str, user: APIKey, timeout=3600):
    cache_key = f"reply:{user.user}:{session_id}:{hash(prompt)}"
    cache.set(cache_key, reply, timeout)


def generate_cache_key(original_key: str) -> str:
    """
    生成安全的缓存键。
    对原始字符串进行哈希处理，确保键长度固定且仅包含安全字符。
    """
    # 使用SHA256哈希函数生成固定长度的键（64位十六进制字符串）
    hash_obj = hashlib.sha256(original_key.encode('utf-8'))
    return hash_obj.hexdigest()
