# 多轮对话功能完整实施规划

## 🎯 **实施范围**

### **高优先级优化（Phase 1）**
1. 上下文长度控制
2. 对话类型识别与自适应响应
3. 智能响应处理

### **中优先级优化（Phase 2）**
1. 对话状态管理
2. 主动对话引导
3. 上下文质量优化

## 📋 **详细实施规划**

### **Phase 1: 基础优化（高优先级）**

#### **Step 1.1: 数据模型扩展**
**目标**: 为多轮对话功能提供数据基础
**预计时间**: 1-2小时

**具体任务**:
1. 扩展`ConversationSession`模型
```python
class ConversationSession(models.Model):
    # 现有字段
    session_id = models.CharField(max_length=100)
    user = models.ForeignKey(APIKey, on_delete=models.CASCADE)
    context = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # 新增字段
    context_summary = models.TextField(blank=True)  # 上下文摘要
    recent_context = models.TextField(blank=True)   # 最近N轮对话
    max_context_length = models.IntegerField(default=4000)  # 最大上下文长度
    conversation_type = models.CharField(max_length=50, default='fault_analysis')  # 对话类型
```

2. 创建`ConversationState`模型
```python
class ConversationState(models.Model):
    session = models.OneToOneField(ConversationSession, on_delete=models.CASCADE)
    current_stage = models.CharField(max_length=50, default='problem_identification')  # 当前阶段
    analysis_depth = models.IntegerField(default=1)  # 分析深度
    user_satisfaction = models.IntegerField(default=0)  # 用户满意度
    last_analysis_result = models.JSONField(null=True, blank=True)  # 上次分析结果
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
```

3. 数据库迁移
```bash
python manage.py makemigrations
python manage.py migrate
```

#### **Step 1.2: 对话类型识别系统**
**目标**: 实现智能对话类型识别
**预计时间**: 2-3小时

**具体任务**:
1. 在`topklogsystem.py`中添加对话类型枚举
```python
from enum import Enum

class ConversationType(Enum):
    FAULT_ANALYSIS = "fault_analysis"        # 故障分析（JSON格式）
    GENERAL_QUESTION = "general_question"    # 一般问题（Markdown格式）
    FOLLOW_UP_QUESTION = "follow_up"         # 跟进问题（Markdown格式）
    EXPLANATION_REQUEST = "explanation"       # 解释请求（Markdown格式）
    PREVENTION_QUESTION = "prevention"       # 预防措施（Markdown格式）
    DEPENDENCY_QUESTION = "dependency"       # 依赖关系（Markdown格式）
```

2. 实现对话类型识别方法
```python
def detect_conversation_type(self, query: str, context: str) -> ConversationType:
    """识别对话类型"""
    query_lower = query.lower()
    
    # 故障分析类问题
    fault_keywords = ["错误", "故障", "异常", "失败", "error", "fatal", "exception"]
    if any(keyword in query_lower for keyword in fault_keywords):
        if len(context) < 100:  # 第一轮对话
            return ConversationType.FAULT_ANALYSIS
        else:
            return ConversationType.FOLLOW_UP_QUESTION
    
    # 预防措施类问题
    prevention_keywords = ["预防", "避免", "防止", "如何避免", "怎么预防"]
    if any(keyword in query_lower for keyword in prevention_keywords):
        return ConversationType.PREVENTION_QUESTION
    
    # 依赖关系类问题
    dependency_keywords = ["依赖", "关系", "调用", "服务", "依赖关系", "调用链"]
    if any(keyword in query_lower for keyword in dependency_keywords):
        return ConversationType.DEPENDENCY_QUESTION
    
    # 解释类问题
    explanation_keywords = ["是什么", "为什么", "如何", "怎么", "什么意思", "解释"]
    if any(keyword in query_lower for keyword in explanation_keywords):
        return ConversationType.EXPLANATION_REQUEST
    
    # 默认情况
    return ConversationType.GENERAL_QUESTION
```

3. 测试对话类型识别准确性

#### **Step 1.3: 自适应Prompt构建系统**
**目标**: 为不同对话类型构建专门的Prompt
**预计时间**: 3-4小时

**具体任务**:
1. 重构`_build_prompt`方法
```python
def _build_prompt(self, query: str, context: Dict) -> List[Dict]:
    # 识别对话类型
    conversation_type = self.detect_conversation_type(query, context.get('context', ''))
    
    # 根据类型构建不同的Prompt
    return self._build_adaptive_prompt(query, context, conversation_type)

def _build_adaptive_prompt(self, query: str, context: Dict, conversation_type: ConversationType) -> List[Dict]:
    """根据对话类型构建不同的Prompt"""
    
    if conversation_type == ConversationType.FAULT_ANALYSIS:
        return self._build_fault_analysis_prompt(query, context)
    elif conversation_type == ConversationType.FOLLOW_UP_QUESTION:
        return self._build_follow_up_prompt(query, context)
    elif conversation_type == ConversationType.PREVENTION_QUESTION:
        return self._build_prevention_prompt(query, context)
    elif conversation_type == ConversationType.DEPENDENCY_QUESTION:
        return self._build_dependency_prompt(query, context)
    elif conversation_type == ConversationType.EXPLANATION_REQUEST:
        return self._build_explanation_prompt(query, context)
    else:
        return self._build_general_prompt(query, context)
```

2. 实现各种Prompt模板
```python
def _build_fault_analysis_prompt(self, query: str, context: Dict) -> List[Dict]:
    """故障分析Prompt（返回JSON）"""
    # 使用现有的故障分析Prompt
    pass

def _build_follow_up_prompt(self, query: str, context: Dict) -> List[Dict]:
    """跟进问题Prompt（返回Markdown）"""
    system_message = f"""
    你是一位资深的系统故障诊断专家。用户正在跟进之前的故障分析，请基于之前的分析结果和当前问题，提供详细的回答。
    
    请用自然语言回答，使用Markdown格式，包含：
    - 直接回答用户的问题
    - 提供相关的技术细节
    - 给出实用的建议
    - 使用列表、代码块等格式增强可读性
    
    不要使用JSON格式，直接输出Markdown内容。
    """
    # ... 构建完整的Prompt

def _build_prevention_prompt(self, query: str, context: Dict) -> List[Dict]:
    """预防措施Prompt（返回Markdown）"""
    system_message = f"""
    你是一位资深的系统运维专家。用户询问如何预防系统故障，请提供详细的预防措施建议。
    
    请用Markdown格式回答，包含：
    - 预防措施分类（监控、配置、代码、流程）
    - 具体的实施建议
    - 最佳实践
    - 工具推荐
    
    使用列表、表格等格式组织内容。
    """
    # ... 构建完整的Prompt
```

#### **Step 1.4: 上下文长度控制**
**目标**: 实现智能上下文管理
**预计时间**: 2-3小时

**具体任务**:
1. 实现上下文压缩方法
```python
def compress_context(self, context: str, max_length: int = 4000) -> str:
    """智能压缩上下文"""
    if len(context) <= max_length:
        return context
    
    # 分割对话轮次
    conversations = context.split('用户：')
    if len(conversations) <= 3:
        return context
    
    # 保留最近3轮对话
    recent_conversations = conversations[-3:]
    recent_context = '用户：'.join(recent_conversations)
    
    # 压缩早期对话为摘要
    early_conversations = conversations[:-3]
    summary = self._generate_context_summary(early_conversations)
    
    return f"{summary}\n\n{recent_context}"

def _generate_context_summary(self, conversations: List[str]) -> str:
    """生成上下文摘要"""
    # 提取关键信息：错误码、服务名、时间等
    key_info = {
        'error_codes': set(),
        'services': set(),
        'time_range': None
    }
    
    for conv in conversations:
        # 使用正则表达式提取关键信息
        pass
    
    return f"## 历史对话摘要\n- 涉及错误码: {', '.join(key_info['error_codes'])}\n- 涉及服务: {', '.join(key_info['services'])}"
```

2. 修改会话更新逻辑
```python
def update_context_with_compression(self, user_input: str, bot_reply: str):
    """带压缩的上下文更新"""
    new_entry = f"用户：{user_input}\n回复：{bot_reply}\n"
    new_context = self.context + new_entry
    
    # 检查是否需要压缩
    if len(new_context) > self.max_context_length:
        compressed_context = self.compress_context(new_context, self.max_context_length)
        self.context = compressed_context
    else:
        self.context = new_context
    
    self.save()
```

#### **Step 1.5: 智能响应处理**
**目标**: 根据对话类型处理响应
**预计时间**: 2-3小时

**具体任务**:
1. 修改`services.py`中的响应处理
```python
def deepseek_r1_api_call(prompt: str, conversation_type: str = "fault_analysis") -> str:
    """调用大模型API，支持不同响应格式"""
    system = TopKLogSystem()
    query = prompt
    result = system.query(query)
    time.sleep(0.5)

    # 获取原始响应
    raw_response = result["response"]
    
    # 根据对话类型处理响应
    if conversation_type == "fault_analysis":
        # 故障分析：转换为JSON格式的Markdown
        return json_to_markdown(raw_response)
    else:
        # 其他类型：直接返回Markdown格式
        return ensure_markdown_format(raw_response)

def ensure_markdown_format(response: str) -> str:
    """确保响应是Markdown格式"""
    # 清理可能的JSON标记
    cleaned_response = response.strip()
    if cleaned_response.startswith('```json'):
        cleaned_response = cleaned_response[7:]
    if cleaned_response.startswith('```'):
        cleaned_response = cleaned_response[3:]
    if cleaned_response.endswith('```'):
        cleaned_response = cleaned_response[:-3]
    
    # 清理HTML标签
    cleaned_response = re.sub(r'<[^>]+>', '', cleaned_response)
    
    # 尝试解析JSON，如果成功则转换
    try:
        json.loads(cleaned_response)
        return json_to_markdown(cleaned_response)
    except json.JSONDecodeError:
        return cleaned_response
```

2. 修改API层传递对话类型
```python
@router.post("/chat", response={200: ChatOut})
def chat(request, data: ChatIn):
    # ... 现有逻辑 ...
    
    # 识别对话类型
    conversation_type = detect_conversation_type(data.user_input, session.context)
    
    # 调用大模型（传递对话类型）
    reply = deepseek_r1_api_call(prompt, conversation_type.value)
    
    # 更新会话状态
    session.conversation_type = conversation_type.value
    session.save()
    
    # ... 其余逻辑 ...
```

### **Phase 2: 智能增强（中优先级）**

#### **Step 2.1: 对话状态管理**
**目标**: 实现对话阶段识别和状态跟踪
**预计时间**: 2-3小时

**具体任务**:
1. 实现对话阶段识别
```python
def detect_conversation_stage(self, context: str) -> str:
    """识别对话阶段"""
    context_lower = context.lower()
    
    if any(keyword in context_lower for keyword in ["解决方案", "怎么解决", "如何修复"]):
        return "solution_seeking"
    elif any(keyword in context_lower for keyword in ["原因", "为什么", "根因"]):
        return "root_cause_analysis"
    elif any(keyword in context_lower for keyword in ["预防", "避免", "防止"]):
        return "prevention_planning"
    else:
        return "problem_identification"
```

2. 实现状态更新逻辑
```python
def update_conversation_state(self, session: ConversationSession, analysis_result: dict):
    """更新对话状态"""
    state, created = ConversationState.objects.get_or_create(
        session=session,
        defaults={
            'current_stage': 'problem_identification',
            'analysis_depth': 1,
            'user_satisfaction': 0
        }
    )
    
    # 更新状态
    state.current_stage = self.detect_conversation_stage(session.context)
    state.last_analysis_result = analysis_result
    state.analysis_depth += 1
    state.save()
```

#### **Step 2.2: 主动对话引导**
**目标**: 实现智能问题生成和建议
**预计时间**: 3-4小时

**具体任务**:
1. 实现问题生成机制
```python
def generate_follow_up_questions(self, analysis_result: dict, conversation_type: str) -> List[str]:
    """基于分析结果生成后续问题"""
    questions = []
    
    if conversation_type == "fault_analysis":
        if analysis_result.get('confidence_level') == 'LOW':
            questions.append("您能提供更多关于这个错误的详细信息吗？")
        if not analysis_result.get('affected_services'):
            questions.append("这个错误影响了哪些服务？")
        if len(analysis_result.get('solutions', {}).get('immediate_actions', [])) < 2:
            questions.append("除了上述解决方案，还有其他建议吗？")
    
    elif conversation_type == "prevention":
        questions.append("这些预防措施的实施优先级如何？")
        questions.append("需要哪些工具来实施这些预防措施？")
    
    return questions

def should_ask_follow_up(self, current_analysis: dict) -> bool:
    """判断是否需要询问后续问题"""
    return (
        current_analysis.get('confidence_level') == 'LOW' or
        len(current_analysis.get('solutions', {}).get('immediate_actions', [])) < 2 or
        not current_analysis.get('monitoring_recommendations')
    )
```

2. 实现主动建议机制
```python
def generate_proactive_suggestions(self, session: ConversationSession) -> List[str]:
    """生成主动建议"""
    suggestions = []
    
    # 基于对话历史生成建议
    if "error" in session.context.lower():
        suggestions.append("建议检查相关服务的监控指标")
        suggestions.append("可以考虑查看错误日志的时间分布")
    
    return suggestions
```

#### **Step 2.3: 上下文质量优化**
**目标**: 提升上下文相关性和信息价值
**预计时间**: 3-4小时

**具体任务**:
1. 实现关键信息提取
```python
def extract_key_information(self, context: str) -> dict:
    """从对话历史中提取关键信息"""
    key_info = {
        'error_codes': set(),
        'services': set(),
        'time_range': None,
        'severity_level': None,
        'keywords': set()
    }
    
    # 使用正则表达式提取错误码
    error_pattern = r'ERROR\s+(\d+)'
    error_codes = re.findall(error_pattern, context)
    key_info['error_codes'].update(error_codes)
    
    # 提取服务名
    service_pattern = r'服务[：:]\s*([^\s\n]+)'
    services = re.findall(service_pattern, context)
    key_info['services'].update(services)
    
    # 提取关键词
    keywords = self._extract_keywords(context)
    key_info['keywords'].update(keywords)
    
    return key_info

def _extract_keywords(self, text: str) -> List[str]:
    """提取关键词"""
    # 使用简单的关键词提取
    keywords = []
    important_words = ["错误", "故障", "异常", "失败", "服务", "数据库", "网络"]
    
    for word in important_words:
        if word in text:
            keywords.append(word)
    
    return keywords
```

2. 实现上下文相关性评估
```python
def assess_context_relevance(self, historical_context: str, current_query: str) -> float:
    """评估历史上下文与当前查询的相关性"""
    # 简单的关键词匹配评估
    historical_keywords = self._extract_keywords(historical_context)
    current_keywords = self._extract_keywords(current_query)
    
    # 计算关键词重叠度
    overlap = len(set(historical_keywords) & set(current_keywords))
    total = len(set(historical_keywords) | set(current_keywords))
    
    if total == 0:
        return 0.0
    
    return overlap / total
```

3. 实现智能上下文过滤
```python
def filter_relevant_context(self, context: str, current_query: str, threshold: float = 0.3) -> str:
    """过滤相关上下文"""
    # 分割对话轮次
    conversations = context.split('用户：')
    
    relevant_conversations = []
    for conv in conversations:
        if self.assess_context_relevance(conv, current_query) >= threshold:
            relevant_conversations.append(conv)
    
    return '用户：'.join(relevant_conversations)
```

## 📅 **实施时间表**

### **Week 1: Phase 1 基础优化**
- **Day 1-2**: Step 1.1 数据模型扩展
- **Day 3-4**: Step 1.2 对话类型识别系统
- **Day 5-7**: Step 1.3 自适应Prompt构建系统

### **Week 2: Phase 1 完成 + Phase 2 开始**
- **Day 1-2**: Step 1.4 上下文长度控制
- **Day 3-4**: Step 1.5 智能响应处理
- **Day 5-7**: Step 2.1 对话状态管理

### **Week 3: Phase 2 智能增强**
- **Day 1-3**: Step 2.2 主动对话引导
- **Day 4-7**: Step 2.3 上下文质量优化

### **Week 4: 测试和优化**
- **Day 1-3**: 功能测试和bug修复
- **Day 4-5**: 性能优化
- **Day 6-7**: 用户体验优化

## 🎯 **成功标准**

### **Phase 1 成功标准**
- ✅ 支持6种对话类型识别，准确率>90%
- ✅ 上下文长度控制在4000字符以内
- ✅ 不同对话类型返回合适格式的响应
- ✅ 故障分析问题返回JSON格式报告
- ✅ 其他问题返回自然语言Markdown回答

### **Phase 2 成功标准**
- ✅ 能够识别对话阶段并调整策略
- ✅ 能够生成相关的后续问题
- ✅ 上下文相关性评估准确率>80%
- ✅ 关键信息提取准确率>85%
- ✅ 用户体验显著提升

## 🚀 **总结**

这个实施规划涵盖了高优先级和中优先级的所有优化，按照依赖关系和重要性排序：

1. **基础优化**：数据模型 → 类型识别 → Prompt构建 → 上下文控制 → 响应处理
2. **智能增强**：状态管理 → 主动引导 → 质量优化

**预计总时间**：3-4周
**核心价值**：解决响应格式单一化问题，提升多轮对话体验
**关键成功因素**：对话类型识别的准确性，上下文管理的智能化

你希望我开始实施哪个步骤？
