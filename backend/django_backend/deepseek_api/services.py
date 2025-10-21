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

def deepseek_r1_api_call(prompt: str, session_context: str = "", conversation_type: str = "fault_analysis") -> str:
    """智能 DeepSeek-R1 API 调用函数"""
    from topklogsystem import TopKLogSystem, ConversationType
    
    system = TopKLogSystem(
        log_path="./data/log",
        llm="deepseek-r1:7b",
        embedding_model="bge-large:latest"
    )

    query = prompt
    
    # 构建上下文信息
    context = {
        'context': session_context,
        'logs': []  # 这里可以添加检索到的日志信息
    }
    
    # 生成响应
    result = system.generate_response(query, context)
    time.sleep(0.5)

    # 获取原始响应
    raw_response = result
    print(f"🔍 原始响应长度: {len(raw_response)} 字符")
    print(f"🔍 对话类型: {conversation_type}")
    print(f"🔍 原始响应前200字符: {raw_response[:200]}...")
    
    # 根据对话类型进行智能处理
    processed_response = process_response_by_type(raw_response, conversation_type)
    print(f"✅ 处理后响应长度: {len(processed_response)} 字符")
    
    return processed_response

def process_response_by_type(response: str, conversation_type: str) -> str:
    """
    根据对话类型智能处理响应
    
    Args:
        response: 原始响应
        conversation_type: 对话类型
        
    Returns:
        str: 处理后的响应
    """
    try:
        # 现在所有对话类型都返回Markdown格式，直接返回
        return response
    except Exception as e:
        print(f"⚠️ 响应处理出错: {e}")
        # 出错时返回原始响应
        return response

def assess_response_quality(response: str, conversation_type: str) -> dict:
    """
    评估响应质量
    
    Args:
        response: 响应内容
        conversation_type: 对话类型
        
    Returns:
        dict: 质量指标
    """
    quality_metrics = {
        'length': len(response),
        'has_structure': False,
        'has_keywords': False,
        'format_correct': False,
        'completeness_score': 0,
        'relevance_score': 0
    }
    
    if not response or len(response.strip()) == 0:
        return quality_metrics
    
    # 检查Markdown结构
    quality_metrics['has_structure'] = any(marker in response for marker in ['#', '##', '###', '-', '*'])
    quality_metrics['format_correct'] = quality_metrics['has_structure']
    
    # 检查关键词（更宽松的关键词匹配）
    keywords = [
        "错误", "故障", "异常", "失败", "服务", "数据库", "网络", "连接", "超时", "内存", "CPU",
        "error", "fatal", "exception", "service", "database", "network", "timeout", "memory",
        "问题", "解决", "分析", "原因", "建议", "监控", "预防", "修复", "优化"
    ]
    keyword_count = sum(response.lower().count(keyword) for keyword in keywords)
    quality_metrics['has_keywords'] = keyword_count > 0
    
    # 计算完整性得分（基于Markdown结构）
    structure_elements = ["#", "##", "###", "-", "*"]
    present_elements = sum(1 for element in structure_elements if element in response)
    quality_metrics['completeness_score'] = min(present_elements / 2, 1.0)  # 至少需要2个结构元素
    
    # 计算相关性得分（基于关键词密度，但更宽松）
    if len(response) > 0:
        keyword_density = keyword_count / len(response)
        # 将密度转换为0-1之间的分数，密度0.01以上就认为相关性较高
        quality_metrics['relevance_score'] = min(keyword_density * 100, 1.0)
    else:
        quality_metrics['relevance_score'] = 0
    
    return quality_metrics

def optimize_response(response: str, conversation_type: str) -> str:
    """
    优化响应内容
    
    Args:
        response: 原始响应
        conversation_type: 对话类型
        
    Returns:
        str: 优化后的响应
    """
    try:
        if conversation_type == "fault_analysis":
            # 故障分析类型：确保JSON格式正确
            return optimize_json_response(response)
        else:
            # 其他类型：优化Markdown格式
            return optimize_markdown_response(response)
    except Exception as e:
        print(f"⚠️ 响应优化出错: {e}")
        return response

def optimize_json_response(response: str) -> str:
    """优化JSON响应"""
    import json
    import re
    
    try:
        # 清理响应
        cleaned_response = re.sub(r'<[^>]+>', '', response)  # 移除HTML标签
        cleaned_response = re.sub(r'```json\s*', '', cleaned_response)  # 移除markdown代码块标记
        cleaned_response = re.sub(r'```\s*$', '', cleaned_response)
        
        # 尝试解析JSON
        json_data = json.loads(cleaned_response)
        
        # 确保所有必需字段存在
        required_fields = {
            "fault_summary": {
                "severity": "MEDIUM",
                "category": "SYSTEM_RESOURCE",
                "description": "系统故障",
                "affected_services": [],
                "error_codes": [],
                "impact_scope": "影响范围未知"
            },
            "root_cause_analysis": {
                "primary_cause": "原因未知",
                "contributing_factors": [],
                "confidence_level": "MEDIUM",
                "reasoning": "分析推理",
                "evidence": []
            },
            "solutions": {
                "immediate_actions": [],
                "long_term_fixes": [],
                "prevention_measures": []
            },
            "monitoring_recommendations": []
        }
        
        # 填充缺失字段
        for field, default_value in required_fields.items():
            if field not in json_data:
                json_data[field] = default_value
            elif isinstance(default_value, dict):
                for sub_field, sub_default in default_value.items():
                    if sub_field not in json_data[field]:
                        json_data[field][sub_field] = sub_default
        
        return json.dumps(json_data, ensure_ascii=False, indent=2)
        
    except json.JSONDecodeError:
        # 如果不是有效JSON，返回原始响应
        return response

def optimize_markdown_response(response: str) -> str:
    """优化Markdown响应"""
    import re
    
    # 清理HTML标签
    cleaned_response = re.sub(r'<[^>]+>', '', response)
    
    # 确保标题格式正确
    lines = cleaned_response.split('\n')
    optimized_lines = []
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        # 确保标题有正确的格式
        if line.startswith('#'):
            # 标题行
            optimized_lines.append(line)
        elif line.startswith('-') or line.startswith('*'):
            # 列表项
            optimized_lines.append(line)
        elif line.startswith('```'):
            # 代码块
            optimized_lines.append(line)
        else:
            # 普通文本
            optimized_lines.append(line)
    
    return '\n'.join(optimized_lines)

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
