# 多轮对话响应格式自适应方案

## 🎯 **问题分析**

### 当前问题
1. **强制JSON格式**：所有回复都被强制转换为故障分析报告的JSON格式
2. **对话类型单一**：无法处理不同类型的对话需求
3. **用户体验差**：非故障分析类问题显示格式不合适

### 具体场景举例
- **第一轮**：用户问"ERROR 500是什么错误？" → 应该返回JSON格式的故障分析报告 ✅
- **第二轮**：用户问"这个错误码可能伴随着哪些别的错误产生？" → 应该返回自然语言回答 ❌
- **第三轮**：用户问"如何预防这类问题？" → 应该返回预防措施列表 ❌
- **第四轮**：用户问"这个服务的依赖关系是什么？" → 应该返回依赖关系图 ❌

## 🔧 **解决方案设计**

### **方案1：对话类型识别 + 自适应响应格式**

#### 1.1 对话类型分类
```python
class ConversationType(Enum):
    FAULT_ANALYSIS = "fault_analysis"        # 故障分析（JSON格式）
    GENERAL_QUESTION = "general_question"    # 一般问题（Markdown格式）
    FOLLOW_UP_QUESTION = "follow_up"         # 跟进问题（Markdown格式）
    EXPLANATION_REQUEST = "explanation"       # 解释请求（Markdown格式）
    PREVENTION_QUESTION = "prevention"       # 预防措施（Markdown格式）
    DEPENDENCY_QUESTION = "dependency"       # 依赖关系（Markdown格式）
```

#### 1.2 对话类型识别逻辑
```python
def detect_conversation_type(self, query: str, context: str) -> ConversationType:
    """识别对话类型"""
    
    # 关键词匹配
    if any(keyword in query.lower() for keyword in ["错误", "故障", "异常", "失败", "error", "fatal"]):
        if len(context) < 100:  # 第一轮对话
            return ConversationType.FAULT_ANALYSIS
        else:
            return ConversationType.FOLLOW_UP_QUESTION
    
    # 预防措施类问题
    if any(keyword in query.lower() for keyword in ["预防", "避免", "防止", "如何避免"]):
        return ConversationType.PREVENTION_QUESTION
    
    # 依赖关系类问题
    if any(keyword in query.lower() for keyword in ["依赖", "关系", "调用", "服务"]):
        return ConversationType.DEPENDENCY_QUESTION
    
    # 解释类问题
    if any(keyword in query.lower() for keyword in ["是什么", "为什么", "如何", "怎么"]):
        return ConversationType.EXPLANATION_REQUEST
    
    # 默认情况
    return ConversationType.GENERAL_QUESTION
```

#### 1.3 自适应Prompt构建
```python
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
    else:
        return self._build_general_prompt(query, context)
```

#### 1.4 不同Prompt模板
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

### **方案2：响应格式自适应处理**

#### 2.1 智能响应处理
```python
def process_response(self, raw_response: str, conversation_type: ConversationType) -> str:
    """根据对话类型处理响应"""
    
    if conversation_type == ConversationType.FAULT_ANALYSIS:
        # 故障分析：转换为JSON格式的Markdown
        return self.json_to_markdown(raw_response)
    else:
        # 其他类型：直接返回Markdown格式
        return self.ensure_markdown_format(raw_response)
```

#### 2.2 Markdown格式确保
```python
def ensure_markdown_format(self, response: str) -> str:
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
        # 如果是JSON，转换为Markdown
        return self.json_to_markdown(cleaned_response)
    except json.JSONDecodeError:
        # 如果不是JSON，直接返回
        return cleaned_response
```

## 🚀 **实施步骤**

### **Step 1: 修改TopKLogSystem**
1. 添加对话类型识别方法
2. 实现自适应Prompt构建
3. 修改query方法支持不同响应格式

### **Step 2: 修改Services层**
1. 更新`deepseek_r1_api_call`方法
2. 实现智能响应处理
3. 添加对话类型传递

### **Step 3: 修改API层**
1. 传递对话类型信息
2. 更新响应处理逻辑

### **Step 4: 测试验证**
1. 测试不同对话类型
2. 验证响应格式正确性
3. 确保前端显示正常

## 📊 **预期效果**

### **改进前**
- 所有回复都是JSON格式的故障分析报告
- 非故障分析问题显示格式不合适
- 用户体验差

### **改进后**
- 故障分析问题：JSON格式的详细报告
- 跟进问题：自然语言的详细回答
- 预防措施：结构化的预防建议
- 依赖关系：清晰的依赖关系说明
- 一般问题：友好的自然语言回答

## 🎯 **具体实现建议**

我建议先实现**对话类型识别**和**自适应响应处理**，这样可以：

1. **保持向后兼容**：现有的故障分析功能不受影响
2. **逐步改进**：可以逐步添加新的对话类型支持
3. **用户体验提升**：不同问题得到合适的回答格式

你希望我先实施哪个部分？我建议从**对话类型识别**开始，这是整个方案的基础。
