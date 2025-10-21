from django.db import models
from django.db.models import F
import string
import random
import time
import logging
logger = logging.getLogger(__name__)

from django.db.models import indexes

class APIKey(models.Model):
    key = models.CharField(max_length=32, unique=True)
    user = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)
    expiry_time = models.IntegerField()  # 过期时间戳
    
    @classmethod
    def generate_key(cls, length=32):
        """生成随机 API Key"""
        characters = string.ascii_letters + string.digits
        return ''.join(random.choice(characters) for _ in range(length))
    
    def is_valid(self):
        """检查 API Key 是否未过期"""
        return time.time() < self.expiry_time
    
    def __str__(self):
        return f"{self.user} - {self.key}"


class RateLimit(models.Model):
    api_key = models.ForeignKey(APIKey, on_delete=models.CASCADE,
                                db_index=True, to_field='key', related_name='rate_limits')
    count = models.IntegerField(default=0)
    reset_time = models.IntegerField()  # 重置时间戳

    class Meta:
        indexes = [
            models.Index(fields=['api_key', 'reset_time'])
        ]
    
    def should_limit(self, max_requests, interval):
        """检查是否应该限制请求"""
        current_time = time.time()
        if current_time > self.reset_time:
            self.count = 0
            self.reset_time = current_time + interval
            self.save()
            return False
        return self.count >= max_requests


class ConversationSession(models.Model):
    session_id = models.CharField(max_length=100)
    # 正确的外键定义：关联 APIKey 的 id（默认）
    user = models.ForeignKey(
        APIKey, 
        on_delete=models.CASCADE, 
        related_name='sessions'
    )
    context = models.TextField(blank=True)
    # 新增字段：多轮对话功能支持
    context_summary = models.TextField(blank=True, help_text="上下文摘要，用于压缩历史对话")
    recent_context = models.TextField(blank=True, help_text="最近N轮对话，保持完整格式")
    max_context_length = models.IntegerField(default=4000, help_text="最大上下文长度限制")
    conversation_type = models.CharField(
        max_length=50, 
        default='fault_analysis',
        choices=[
            ('fault_analysis', '故障分析'),
            ('general_question', '一般问题'),
            ('follow_up', '跟进问题'),
            ('explanation', '解释请求'),
            ('prevention', '预防措施'),
            ('dependency', '依赖关系'),
        ],
        help_text="当前对话类型"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ('session_id', 'user')  # 确保用户+会话ID唯一
    
    def update_context(self, user_input, bot_reply):
        """原子更新上下文，避免并发覆盖"""
        new_entry = f"用户：{user_input}\n回复：{bot_reply}\n"
        # 数据库层面拼接，而非内存中
        ConversationSession.objects.filter(
            pk=self.pk,  # 精确匹配当前会话
            user=self.user  # 确保用户一致
        ).update(context=F('context') + new_entry)
        # 刷新实例，获取更新后的值
        self.refresh_from_db()

        # import logging
        # logger = logging.getLogger(__name__)
        # logger.info(f"更新会话 {self.session_id}（用户：{self.user.key}）：{new_entry}")
    
    def clear_context(self):
        """清空对话上下文"""
        self.context = ""
        self.context_summary = ""
        self.recent_context = ""
        self.save()
    
    def compress_context_if_needed(self, max_length: int = None):
        """检查并压缩上下文（如果需要）"""
        if max_length is None:
            max_length = self.max_context_length
        
        if len(self.context) <= max_length:
            return False
        
        # 需要压缩上下文
        self._compress_context()
        return True
    
    def _compress_context(self):
        """智能压缩上下文，保留最近对话并生成摘要"""
        import re
        
        # 分割对话轮次
        conversations = self.context.split('用户：')
        if len(conversations) <= 3:
            return
        
        # 智能决定保留轮数（基于上下文长度）
        total_length = len(self.context)
        if total_length > self.max_context_length * 2:
            # 如果上下文很长，只保留最近2轮
            keep_rounds = 2
        else:
            # 否则保留最近3轮
            keep_rounds = 3
        
        # 保留最近对话
        recent_conversations = conversations[-keep_rounds:]
        self.recent_context = '用户：'.join(recent_conversations)
        
        # 压缩早期对话为摘要
        early_conversations = conversations[:-keep_rounds]
        self.context_summary = self._generate_context_summary(early_conversations)
        
        # 更新完整上下文
        compressed_context = f"{self.context_summary}\n\n{self.recent_context}"
        
        # 如果压缩后仍然太长，进行二次压缩
        if len(compressed_context) > self.max_context_length:
            compressed_context = self._secondary_compress(compressed_context)
        
        self.context = compressed_context
        self.save()
    
    def _generate_context_summary(self, conversations):
        """智能生成上下文摘要"""
        import re
        
        # 提取关键信息
        key_info = {
            'error_codes': set(),
            'services': set(),
            'keywords': set(),
            'time_patterns': set(),
            'user_patterns': set(),
            'topics': set()
        }
        
        for conv in conversations:
            # 提取错误码
            error_patterns = [
                r'ERROR\s+(\d+)',
                r'FATAL\s+(\d+)',
                r'Exception:\s*(\w+)',
                r'错误码[：:]\s*(\w+)'
            ]
            for pattern in error_patterns:
                matches = re.findall(pattern, conv, re.IGNORECASE)
                key_info['error_codes'].update(matches)
            
            # 提取服务名
            service_patterns = [
                r'服务[：:]\s*([^\s\n]+)',
                r'Service[：:]\s*([^\s\n]+)',
                r'模块[：:]\s*([^\s\n]+)',
                r'组件[：:]\s*([^\s\n]+)'
            ]
            for pattern in service_patterns:
                matches = re.findall(pattern, conv, re.IGNORECASE)
                key_info['services'].update(matches)
            
            # 提取时间模式
            time_patterns = [
                r'\d{4}-\d{2}-\d{2}',
                r'\d{2}:\d{2}:\d{2}',
                r'(\d+)\s*分钟前',
                r'(\d+)\s*小时前'
            ]
            for pattern in time_patterns:
                matches = re.findall(pattern, conv)
                key_info['time_patterns'].update(matches)
            
            # 提取用户模式
            user_patterns = [
                r'用户[：:]\s*([^\s\n]+)',
                r'User[：:]\s*([^\s\n]+)',
                r'用户ID[：:]\s*([^\s\n]+)'
            ]
            for pattern in user_patterns:
                matches = re.findall(pattern, conv, re.IGNORECASE)
                key_info['user_patterns'].update(matches)
            
            # 提取关键词和主题
            important_words = [
                "错误", "故障", "异常", "失败", "服务", "数据库", "网络",
                "连接", "超时", "内存", "CPU", "磁盘", "日志", "监控",
                "告警", "恢复", "重启", "部署", "发布", "回滚"
            ]
            for word in important_words:
                if word in conv:
                    key_info['keywords'].add(word)
            
            # 提取主题（基于对话内容）
            if "数据库" in conv:
                key_info['topics'].add("数据库问题")
            if "网络" in conv:
                key_info['topics'].add("网络问题")
            if "内存" in conv or "CPU" in conv:
                key_info['topics'].add("性能问题")
            if "部署" in conv or "发布" in conv:
                key_info['topics'].add("部署问题")
        
        # 构建智能摘要
        summary_parts = ["## 📋 历史对话摘要"]
        
        # 主题摘要
        if key_info['topics']:
            summary_parts.append(f"**讨论主题**: {', '.join(key_info['topics'])}")
        
        # 错误码摘要
        if key_info['error_codes']:
            error_codes_str = ', '.join(list(key_info['error_codes'])[:5])  # 最多显示5个
            if len(key_info['error_codes']) > 5:
                error_codes_str += f" 等{len(key_info['error_codes'])}个错误码"
            summary_parts.append(f"**涉及错误码**: {error_codes_str}")
        
        # 服务摘要
        if key_info['services']:
            services_str = ', '.join(list(key_info['services'])[:3])  # 最多显示3个
            if len(key_info['services']) > 3:
                services_str += f" 等{len(key_info['services'])}个服务"
            summary_parts.append(f"**涉及服务**: {services_str}")
        
        # 关键词摘要
        if key_info['keywords']:
            keywords_str = ', '.join(list(key_info['keywords'])[:8])  # 最多显示8个
            summary_parts.append(f"**关键词**: {keywords_str}")
        
        # 时间模式摘要
        if key_info['time_patterns']:
            summary_parts.append(f"**时间范围**: 包含{len(key_info['time_patterns'])}个时间点")
        
        # 用户模式摘要
        if key_info['user_patterns']:
            summary_parts.append(f"**涉及用户**: {len(key_info['user_patterns'])}个用户")
        
        # 添加对话轮数统计
        summary_parts.append(f"**对话轮数**: {len(conversations)}轮")
        
        return '\n'.join(summary_parts)
    
    def _secondary_compress(self, context: str) -> str:
        """二次压缩，进一步减少上下文长度"""
        import re
        
        # 移除多余的空行
        context = re.sub(r'\n\s*\n\s*\n', '\n\n', context)
        
        # 压缩长句子（保留关键信息）
        lines = context.split('\n')
        compressed_lines = []
        
        for line in lines:
            if len(line) > 200:
                # 长句子压缩：保留前100字符和后50字符
                compressed_line = line[:100] + "..." + line[-50:]
                compressed_lines.append(compressed_line)
            else:
                compressed_lines.append(line)
        
        # 重新组合
        compressed_context = '\n'.join(compressed_lines)
        
        # 如果还是太长，只保留最近的内容
        if len(compressed_context) > self.max_context_length:
            # 按段落分割，保留最后几个段落
            paragraphs = compressed_context.split('\n\n')
            keep_paragraphs = []
            current_length = 0
            
            # 从后往前添加段落
            for paragraph in reversed(paragraphs):
                if current_length + len(paragraph) <= self.max_context_length * 0.8:
                    keep_paragraphs.insert(0, paragraph)
                    current_length += len(paragraph)
                else:
                    break
            
            compressed_context = '\n\n'.join(keep_paragraphs)
        
        return compressed_context
    
    def assess_context_quality(self) -> dict:
        """评估上下文质量"""
        context = self.context
        
        # 计算质量指标
        quality_metrics = {
            'length': len(context),
            'conversation_rounds': len(context.split('用户：')) - 1,
            'has_summary': bool(self.context_summary),
            'has_recent_context': bool(self.recent_context),
            'compression_ratio': 0,
            'information_density': 0,
            'relevance_score': 0
        }
        
        # 计算压缩比
        if self.context_summary and self.recent_context:
            original_length = len(self.context_summary) + len(self.recent_context)
            compressed_length = len(context)
            quality_metrics['compression_ratio'] = compressed_length / original_length if original_length > 0 else 1
        
        # 计算信息密度（关键词密度）
        import re
        keywords = ["错误", "故障", "异常", "失败", "服务", "数据库", "网络", "连接", "超时"]
        keyword_count = sum(context.lower().count(keyword) for keyword in keywords)
        quality_metrics['information_density'] = keyword_count / len(context) if len(context) > 0 else 0
        
        # 计算相关性得分（基于错误码和服务名）
        error_codes = len(re.findall(r'ERROR\s+(\d+)', context))
        services = len(re.findall(r'服务[：:]\s*([^\s\n]+)', context))
        quality_metrics['relevance_score'] = (error_codes + services) / len(context) if len(context) > 0 else 0
        
        return quality_metrics
    
    def optimize_context_length(self, target_length: int = None) -> bool:
        """优化上下文长度到目标长度"""
        if target_length is None:
            target_length = self.max_context_length
        
        current_length = len(self.context)
        if current_length <= target_length:
            return False
        
        # 计算需要压缩的比例
        compression_ratio = target_length / current_length
        
        if compression_ratio < 0.5:
            # 需要大幅压缩，使用激进策略
            self._aggressive_compress(target_length)
        elif compression_ratio < 0.8:
            # 需要中等压缩，使用标准策略
            self._compress_context()
        else:
            # 需要轻微压缩，使用保守策略
            self._conservative_compress(target_length)
        
        return True
    
    def _aggressive_compress(self, target_length: int):
        """激进压缩策略"""
        # 只保留最近1轮对话
        conversations = self.context.split('用户：')
        if len(conversations) > 1:
            recent_conversation = conversations[-1]
            self.recent_context = f"用户：{recent_conversation}"
            
            # 生成高度压缩的摘要
            early_conversations = conversations[:-1]
            self.context_summary = self._generate_compact_summary(early_conversations)
            
            # 更新上下文
            self.context = f"{self.context_summary}\n\n{self.recent_context}"
            
            # 如果还是太长，进行二次压缩
            if len(self.context) > target_length:
                self.context = self._secondary_compress(self.context)
            
            self.save()
    
    def _conservative_compress(self, target_length: int):
        """保守压缩策略"""
        # 移除多余的空行和重复内容
        import re
        context = self.context
        
        # 移除多余空行
        context = re.sub(r'\n\s*\n\s*\n', '\n\n', context)
        
        # 移除重复的短语
        lines = context.split('\n')
        seen_lines = set()
        unique_lines = []
        
        for line in lines:
            line_key = line.strip().lower()
            if line_key not in seen_lines and len(line_key) > 10:
                seen_lines.add(line_key)
                unique_lines.append(line)
        
        self.context = '\n'.join(unique_lines)
        
        # 如果还是太长，进行二次压缩
        if len(self.context) > target_length:
            self.context = self._secondary_compress(self.context)
        
        self.save()
    
    def _generate_compact_summary(self, conversations):
        """生成高度压缩的摘要"""
        import re
        
        # 只提取最关键的信息
        key_info = {
            'error_codes': set(),
            'services': set(),
            'topics': set()
        }
        
        for conv in conversations:
            # 提取错误码
            error_codes = re.findall(r'ERROR\s+(\d+)', conv)
            key_info['error_codes'].update(error_codes[:3])  # 最多3个
            
            # 提取服务名
            services = re.findall(r'服务[：:]\s*([^\s\n]+)', conv)
            key_info['services'].update(services[:2])  # 最多2个
            
            # 提取主题
            if "数据库" in conv:
                key_info['topics'].add("数据库")
            if "网络" in conv:
                key_info['topics'].add("网络")
            if "性能" in conv:
                key_info['topics'].add("性能")
        
        # 构建紧凑摘要
        summary_parts = ["## 历史摘要"]
        
        if key_info['topics']:
            summary_parts.append(f"主题: {', '.join(key_info['topics'])}")
        
        if key_info['error_codes']:
            summary_parts.append(f"错误码: {', '.join(key_info['error_codes'])}")
        
        if key_info['services']:
            summary_parts.append(f"服务: {', '.join(key_info['services'])}")
        
        summary_parts.append(f"轮数: {len(conversations)}")
        
        return '\n'.join(summary_parts)
    
    def update_context_with_compression(self, user_input: str, bot_reply: str):
        """带压缩的上下文更新"""
        new_entry = f"用户：{user_input}\n回复：{bot_reply}\n"
        new_context = self.context + new_entry
        
        # 检查是否需要压缩
        if len(new_context) > self.max_context_length:
            self.context = new_context
            self._compress_context()
        else:
            self.context = new_context
            self.save()
    
    def get_or_create_state(self):
        """获取或创建对话状态"""
        from .models import ConversationState
        state, created = ConversationState.objects.get_or_create(
            session=self,
            defaults={
                'current_stage': 'problem_identification',
                'analysis_depth': 1,
                'user_satisfaction': 0
            }
        )
        return state
    
    def __str__(self):
        return self.session_id


class ConversationState(models.Model):
    """对话状态管理模型，用于跟踪对话阶段和分析状态"""
    session = models.OneToOneField(
        ConversationSession, 
        on_delete=models.CASCADE,
        related_name='state',
        help_text="关联的对话会话"
    )
    current_stage = models.CharField(
        max_length=50, 
        default='problem_identification',
        choices=[
            ('problem_identification', '问题识别'),
            ('root_cause_analysis', '根因分析'),
            ('solution_seeking', '解决方案寻求'),
            ('prevention_planning', '预防规划'),
            ('follow_up', '跟进讨论'),
        ],
        help_text="当前对话阶段"
    )
    analysis_depth = models.IntegerField(
        default=1,
        help_text="分析深度，表示对话轮次"
    )
    user_satisfaction = models.IntegerField(
        default=0,
        help_text="用户满意度评分 (0-5)"
    )
    last_analysis_result = models.JSONField(
        null=True, 
        blank=True,
        help_text="上次分析结果，用于状态跟踪"
    )
    key_information = models.JSONField(
        default=dict,
        help_text="提取的关键信息（错误码、服务名等）"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "对话状态"
        verbose_name_plural = "对话状态"
    
    def update_stage(self, new_stage: str):
        """更新对话阶段"""
        self.current_stage = new_stage
        self.analysis_depth += 1
        self.save()
    
    def update_satisfaction(self, satisfaction: int):
        """更新用户满意度"""
        if 0 <= satisfaction <= 5:
            self.user_satisfaction = satisfaction
            self.save()
    
    def update_key_information(self, key_info: dict):
        """更新关键信息"""
        self.key_information = key_info
        self.save()
    
    def __str__(self):
        return f"{self.session.session_id} - {self.current_stage}"
