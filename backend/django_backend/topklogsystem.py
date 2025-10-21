import os

# chroma 不上传数据
os.environ["ANONYMIZED_TELEMETRY"] = "false"
os.environ["DISABLE_TELEMETRY"] = "1"
os.environ["CHROMA_TELEMETRY_ENABLED"] = "false"

import json
import logging
import pandas as pd
import re
from typing import Any, Dict, List
from enum import Enum

# langchain
from langchain.prompts import ChatPromptTemplate, HumanMessagePromptTemplate, SystemMessagePromptTemplate
from langchain_ollama import OllamaLLM, OllamaEmbeddings

# llama-index & chroma
import chromadb
from llama_index.core import Settings  # 全局
from llama_index.core import Document
from llama_index.core import VectorStoreIndex, SimpleDirectoryReader, StorageContext
from llama_index.vector_stores.chroma import ChromaVectorStore  # 注意导入路径

# 导入领域知识
from domain_knowledge import (
    get_error_code_meaning, 
    get_service_dependencies, 
    get_fault_category,
    get_severity_level,
    get_common_pattern_info,
    get_monitoring_recommendations,
    get_expert_insights,
    get_industry_standards,
    get_best_practices,
    FAULT_CATEGORIES,
    COMMON_PATTERNS
)

# 日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ConversationType(Enum):
    """对话类型枚举"""
    FAULT_ANALYSIS = "fault_analysis"        # 故障分析（Markdown格式）
    GENERAL_QUESTION = "general_question"    # 一般问题（Markdown格式）
    FOLLOW_UP_QUESTION = "follow_up"         # 跟进问题（Markdown格式）
    EXPLANATION_REQUEST = "explanation"       # 解释请求（Markdown格式）
    PREVENTION_QUESTION = "prevention"       # 预防措施（Markdown格式）
    DEPENDENCY_QUESTION = "dependency"       # 依赖关系（Markdown格式）


class TopKLogSystem:
    def __init__(
            self,
            log_path: str,
            llm: str,
            embedding_model: str,
    ) -> None:
        # init models
        self.embedding_model = OllamaEmbeddings(model=embedding_model)

        self.llm = OllamaLLM(model=llm, temperature=0.1)

        # init database
        Settings.llm = self.llm
        Settings.embed_model = self.embedding_model  # 全局设置

        self.log_path = log_path
        self.log_index = None
        self.vector_store = None
        self._build_vectorstore()  # 直接构建

    # 加载数据并构建索引
    def _build_vectorstore(self):
        vector_store_path = "./data/vector_stores"
        os.makedirs(vector_store_path, exist_ok=True)  # exist_ok=True 目录存在时不报错

        chroma_client = chromadb.PersistentClient(path=vector_store_path)  # chromadb 持久化

        # ChromaVectorStore 将 collection 与 store 绑定
        # 也是将 Chroma 包装为 llama-index 的接口
        # StorageContext存储上下文， 包含 Vector Store、Document Store、Index Store 等
        log_collection = chroma_client.get_or_create_collection("log_collection")

        # 构建 log 库 index
        log_vector_store = ChromaVectorStore(chroma_collection=log_collection)
        log_storage_context = StorageContext.from_defaults(vector_store=log_vector_store)
        
        # 检查是否已经存在索引
        try:
            # 尝试从现有存储加载索引
            if log_collection.count() > 0:
                logger.info(f"发现现有索引，包含 {log_collection.count()} 条记录")
                self.log_index = VectorStoreIndex.from_vector_store(
                    log_vector_store,
                    storage_context=log_storage_context,
                    show_progress=True,
                )
                logger.info("成功加载现有日志库索引")
                return
        except Exception as e:
            logger.warning(f"加载现有索引失败: {e}，将重新构建")
        
        # 如果不存在索引或加载失败，重新构建
        if log_documents := self._load_documents(self.log_path):
            self.log_index = VectorStoreIndex.from_documents(
                log_documents,
                storage_context=log_storage_context,
                show_progress=True,
            )
            logger.info(f"日志库索引构建完成，共 {len(log_documents)} 条日志")

    @staticmethod
    # 加载文档数据
    def _load_documents(data_path: str) -> List[Document]:
        if not os.path.exists(data_path):
            logger.warning(f"数据路径不存在: {data_path}")
            return []

        documents = []
        for file in os.listdir(data_path):
            ext = os.path.splitext(file)[1]
            if ext not in [".txt", ".md", ".json", ".jsonl", ".csv"]:
                continue

            file_path = f"{data_path}/{file}"
            try:
                if ext == ".csv":  # utf-8 的 csv
                    # 大型 csv 分块进行读取
                    chunk_size = 1000  # 每次读取1000行
                    for chunk in pd.read_csv(file_path, chunksize=chunk_size):
                        for row in chunk.itertuples(index=False):  # 无行号
                            content = str(row).replace("Pandas", " ")
                            documents.append(Document(text=content))
                else:  # .txt or .md, .json
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                        doc = Document(text=content, )
                        documents.append(doc)
            except Exception as e:
                logger.error(f"加载文档失败 {file_path}: {e}")
        return documents

        # 检索相关日志

    def retrieve_logs(self, query: str, top_k: int = 10) -> List[Dict]:
        """
        多策略智能检索日志
        """
        if not self.log_index:
            return []

        try:
            # 策略1: 语义相似度检索
            semantic_results = self._semantic_retrieval(query, top_k)
            
            # 策略2: 关键词精确匹配
            keyword_results = self._keyword_retrieval(query, top_k)
            
            # 策略3: 错误码匹配
            error_code_results = self._error_code_retrieval(query, top_k)
            
            # 合并和去重结果
            all_results = semantic_results + keyword_results + error_code_results
            filtered_results = self._deduplicate_and_rank(all_results, top_k)
            
            return filtered_results
        except Exception as e:
            logger.error(f"日志检索失败: {e}")
            return []

    def _semantic_retrieval(self, query: str, top_k: int) -> List[Dict]:
        """语义相似度检索"""
        try:
            retriever = self.log_index.as_retriever(similarity_top_k=top_k)
            results = retriever.retrieve(query)

            formatted_results = []
            for result in results:
                formatted_results.append({
                    "content": result.text,
                    "score": result.score,
                    "retrieval_method": "semantic"
                })
            return formatted_results
        except Exception as e:
            logger.error(f"语义检索失败: {e}")
            return []

    def _keyword_retrieval(self, query: str, top_k: int) -> List[Dict]:
        """关键词精确匹配检索"""
        try:
            # 提取查询中的关键词
            keywords = self._extract_keywords(query)
            if not keywords:
                return []
            
            # 使用关键词进行检索
            keyword_query = " ".join(keywords)
            retriever = self.log_index.as_retriever(similarity_top_k=top_k)
            results = retriever.retrieve(keyword_query)
            
            formatted_results = []
            for result in results:
                # 计算关键词匹配度
                keyword_score = self._calculate_keyword_score(result.text, keywords)
                if keyword_score > 0.3:  # 关键词匹配阈值
                    formatted_results.append({
                        "content": result.text,
                        "score": keyword_score,
                        "retrieval_method": "keyword"
                    })
            return formatted_results
        except Exception as e:
            logger.error(f"关键词检索失败: {e}")
            return []

    def _error_code_retrieval(self, query: str, top_k: int) -> List[Dict]:
        """错误码精确匹配检索"""
        try:
            # 提取查询中的错误码
            error_codes = self._extract_error_codes(query)
            if not error_codes:
                return []
            
            # 使用错误码进行检索
            error_query = " ".join(error_codes)
            retriever = self.log_index.as_retriever(similarity_top_k=top_k)
            results = retriever.retrieve(error_query)
            
            formatted_results = []
            for result in results:
                # 检查是否包含错误码
                if any(code in result.text for code in error_codes):
                    formatted_results.append({
                        "content": result.text,
                        "score": 1.0,  # 精确匹配给最高分
                        "retrieval_method": "error_code"
                    })
            return formatted_results
        except Exception as e:
            logger.error(f"错误码检索失败: {e}")
            return []

    def _extract_keywords(self, query: str) -> List[str]:
        """提取查询关键词"""
        import re
        # 提取中文和英文关键词
        keywords = []
        
        # 提取中文词汇（2-4个字符）
        chinese_words = re.findall(r'[\u4e00-\u9fff]{2,4}', query)
        keywords.extend(chinese_words)
        
        # 提取英文词汇（3个字符以上）
        english_words = re.findall(r'\b[A-Za-z]{3,}\b', query)
        keywords.extend(english_words)
        
        # 提取技术术语
        tech_terms = ['数据库', '连接池', '认证', '支付', '库存', '订单', '用户', '服务']
        for term in tech_terms:
            if term in query:
                keywords.append(term)
        
        return list(set(keywords))  # 去重

    def _calculate_keyword_score(self, text: str, keywords: List[str]) -> float:
        """计算关键词匹配分数"""
        if not keywords:
            return 0.0
        
        matches = 0
        for keyword in keywords:
            if keyword.lower() in text.lower():
                matches += 1
        
        return matches / len(keywords)

    def _deduplicate_and_rank(self, all_results: List[Dict], top_k: int) -> List[Dict]:
        """去重和排序结果"""
        # 按内容去重
        seen_contents = set()
        unique_results = []
        
        for result in all_results:
            content_hash = hash(result["content"])
            if content_hash not in seen_contents:
                seen_contents.add(content_hash)
                unique_results.append(result)
        
        # 按分数排序
        unique_results.sort(key=lambda x: x["score"], reverse=True)
        
        # 返回前top_k个结果
        return unique_results[:top_k]

    def detect_conversation_type(self, query: str, context: str = "") -> ConversationType:
        """
        识别对话类型
        
        Args:
            query: 用户当前查询
            context: 对话历史上下文
            
        Returns:
            ConversationType: 识别出的对话类型
        """
        query_lower = query.lower()
        context_lower = context.lower()
        
        # 1. 故障分析类问题（优先级最高，包含错误码的查询）
        fault_keywords = [
            "错误", "故障", "异常", "失败", "error", "fatal", "exception", 
            "报错", "出错", "问题", "bug", "issue", "crash", "down"
        ]
        
        # 检查是否包含错误码模式（如：Alatest97, ERROR, FATAL等）
        error_code_patterns = [
            r'[A-Za-z]+\d+',  # 如 Alatest97
            r'\b(ERROR|FATAL|WARN|INFO|DEBUG)\b',  # 日志级别
            r'\b[A-Z_]+\b'  # 大写错误码
        ]
        
        has_error_code = any(re.search(pattern, query) for pattern in error_code_patterns)
        
        if has_error_code or any(keyword in query_lower for keyword in fault_keywords):
            # 如果是第一轮对话或上下文很短，认为是故障分析
            if len(context) < 100 or not context.strip():
                return ConversationType.FAULT_ANALYSIS
            else:
                # 有历史对话，认为是跟进问题
                return ConversationType.FOLLOW_UP_QUESTION
        
        # 2. 预防措施类问题（优先级第二）
        prevention_keywords = [
            "预防", "避免", "防止", "如何避免", "怎么预防", "预防措施",
            "避免", "防范", "预防性", "proactive", "prevention", "avoid"
        ]
        
        if any(keyword in query_lower for keyword in prevention_keywords):
            return ConversationType.PREVENTION_QUESTION
        
        # 3. 解释类问题（优先级第三）
        explanation_keywords = [
            "是什么", "为什么", "什么意思", "解释", "说明", "这个", "这个错误"
        ]
        
        # 特殊处理：如果包含"是什么"、"为什么"等，优先判断为解释请求
        if any(keyword in query_lower for keyword in explanation_keywords):
            return ConversationType.EXPLANATION_REQUEST
        
        # 4. 依赖关系类问题（优先级第四）
        dependency_keywords = [
            "依赖", "关系", "调用", "服务", "依赖关系", "调用链", "依赖链",
            "关联", "连接", "dependencies", "relationship", "call", "service"
        ]
        
        # 特殊处理：避免"数据库连接"被误判为依赖关系
        if any(keyword in query_lower for keyword in dependency_keywords):
            # 排除故障相关词汇
            if not any(keyword in query_lower for keyword in ["失败", "错误", "异常", "故障"]):
                return ConversationType.DEPENDENCY_QUESTION
        
        # 5. 基于上下文的判断
        if context:
            # 如果上下文包含故障分析相关内容，可能是跟进问题
            if any(keyword in context_lower for keyword in fault_keywords):
                return ConversationType.FOLLOW_UP_QUESTION
            
            # 如果上下文包含预防相关内容，可能是预防问题
            if any(keyword in context_lower for keyword in prevention_keywords):
                return ConversationType.PREVENTION_QUESTION
        
        # 6. 特殊处理：包含"如何"或"怎么"但不是预防措施
        if any(keyword in query_lower for keyword in ["如何", "怎么"]):
            # 检查是否包含预防相关词汇
            if not any(keyword in query_lower for keyword in ["预防", "避免", "防止"]):
                return ConversationType.EXPLANATION_REQUEST
        
        # 7. 默认情况
        return ConversationType.GENERAL_QUESTION

    def generate_response(self, query: str, context: Dict) -> str:
        """
        生成响应，支持对话类型识别
        
        Args:
            query: 用户查询
            context: 上下文信息（包含对话历史）
            
        Returns:
            str: LLM响应
        """
        # 识别对话类型
        conversation_type = self.detect_conversation_type(query, context.get('context', ''))
        
        # 检索相关日志
        try:
            logs = self.retrieve_logs(query, top_k=5)
            context['logs'] = logs
        except Exception as e:
            logger.error(f"日志检索失败: {e}")
            context['logs'] = []
        
        # 根据对话类型构建不同的Prompt
        prompt = self._build_adaptive_prompt(query, context, conversation_type)

        try:
            response = self.llm.invoke(prompt)  # 调用LLM
            return response
        except Exception as e:
            logger.error(f"LLM调用失败: {e}")
            return f"生成响应时出错: {str(e)}"

    def _build_adaptive_prompt(self, query: str, context: Dict, conversation_type: ConversationType) -> List[Dict]:
        """
        根据对话类型构建不同的Prompt
        
        Args:
            query: 用户查询
            context: 上下文信息
            conversation_type: 对话类型
            
        Returns:
            List[Dict]: Prompt消息列表
        """
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

    def _build_fault_analysis_prompt(self, query: str, context: Dict) -> List[Dict]:
        """构建故障分析Prompt（返回Markdown格式）"""
        # 构建领域知识上下文
        domain_context = self._build_domain_context(context)
        
        # 构建日志上下文
        log_context = self._build_structured_context(context)
        
        system_message = SystemMessagePromptTemplate.from_template(f"""
你是一位资深的电商系统故障诊断专家，具有15年以上的日志分析和故障排查经验。你的任务是基于提供的日志信息，进行专业、准确的故障分析。

## 领域知识背景
{domain_context}

## 专业分析框架
请按照以下三个步骤进行结构化分析：

### 第一步：故障现象识别 🔍
- **错误级别识别**: 准确识别日志中的错误级别（FATAL/ERROR/WARN/INFO/DEBUG）
- **关键信息提取**: 提取错误码、服务名称、时间戳、用户ID等关键信息
- **影响范围评估**: 分析故障影响的服务、用户群体和业务功能
- **严重程度判断**: 基于业务影响和技术影响评估严重程度

### 第二步：根因分析 🧠
- **直接原因分析**: 基于错误码和日志内容分析直接触发原因
- **根本原因挖掘**: 深入分析导致故障的系统性、架构性问题
- **依赖关系考虑**: 分析服务间依赖关系、调用链和数据流
- **环境因素识别**: 考虑网络、硬件、配置、数据等环境因素
- **置信度评估**: 基于证据充分性提供置信度（HIGH/MEDIUM/LOW）

### 第三步：解决方案建议 🛠️
- **紧急修复措施**: 提供立即可执行的修复方案，按优先级排序
- **长期优化方案**: 建议系统架构、代码、配置等方面的根本性改进
- **预防措施**: 提供避免类似故障再次发生的预防性措施
- **监控建议**: 建议监控指标、告警规则和运维流程

## 输出格式要求
请使用Markdown格式输出分析结果，确保结构清晰、层次分明：

### 📋 内容要求
- **直接回答**: 直接、明确地回答用户的问题
- **技术细节**: 提供相关的技术细节和背景信息
- **实用建议**: 给出具体、可操作的建议
- **专业深度**: 展现专业的技术深度和行业经验

### 📝 格式要求
- 使用Markdown格式组织内容
- 使用标题、列表、代码块等增强可读性
- 使用emoji图标突出重点信息
- 保持结构清晰，层次分明

**重要**: 不要使用JSON格式，直接输出Markdown内容。
        """)

        user_message = HumanMessagePromptTemplate.from_template("""
## 相关日志信息
{log_context}

## 分析任务
用户问题：{query}

请基于以上日志信息，按照分析框架进行专业的故障诊断分析，使用Markdown格式输出结果。
        """)

        prompt = ChatPromptTemplate.from_messages([
            system_message,
            user_message
        ])

        return prompt.format_prompt(
            log_context=log_context,
            query=query
        ).to_messages()

    def _build_structured_context(self, context) -> str:
        """
        构建智能化的日志上下文，提高信息利用效率
        """
        # 处理不同类型的context
        if isinstance(context, str):
            # 如果是字符串，直接返回
            return f"## 相关日志信息\n{context}"
        
        if not context or not isinstance(context, (list, dict)):
            return "## 相关日志信息\n未找到相关日志信息。"
        
        # 如果是字典，尝试获取logs
        if isinstance(context, dict):
            logs = context.get('logs', [])
            if not logs:
                return "## 相关日志信息\n暂无相关日志信息。"
        else:
            logs = context
        
        # 智能过滤和排序
        filtered_context = self._intelligent_context_filter(logs)
        
        log_context = "## 相关日志信息\n\n"
        
        # 按检索方法和相关性分组
        semantic_logs = [log for log in filtered_context if log.get('retrieval_method') == 'semantic']
        keyword_logs = [log for log in filtered_context if log.get('retrieval_method') == 'keyword']
        error_code_logs = [log for log in filtered_context if log.get('retrieval_method') == 'error_code']
        
        # 优先显示错误码精确匹配的日志
        if error_code_logs:
            log_context += "### 🔍 精确匹配的日志\n"
            for i, log in enumerate(error_code_logs[:3], 1):
                log_context += self._format_log_entry(log, i, "精确匹配")
        
        # 显示关键词匹配的日志
        if keyword_logs:
            log_context += "\n### 🔑 关键词匹配的日志\n"
            for i, log in enumerate(keyword_logs[:3], 1):
                log_context += self._format_log_entry(log, i, "关键词匹配")
        
        # 显示语义相似的日志
        if semantic_logs:
            log_context += "\n### 🧠 语义相似的日志\n"
            for i, log in enumerate(semantic_logs[:3], 1):
                log_context += self._format_log_entry(log, i, "语义相似")
        
        return log_context

    def _intelligent_context_filter(self, context: List[Dict]) -> List[Dict]:
        """
        智能上下文过滤
        """
        filtered_logs = []
        
        for log in context:
            content = log.get('content', '')
            score = log.get('score', 0)
            
            # 过滤条件
            if score < 0.1:  # 相关性太低
                continue
            
            # 提取关键信息
            log_level = self._extract_log_level(content)
            error_codes = self._extract_error_codes(content)
            services = self._extract_services(content)
            
            # 计算信息价值分数
            value_score = self._calculate_information_value(content, log_level, error_codes, services)
            
            if value_score > 0.3:  # 信息价值阈值
                log['value_score'] = value_score
                log['log_level'] = log_level
                log['error_codes'] = error_codes
                log['services'] = services
                filtered_logs.append(log)
        
        # 按价值分数和相关性分数综合排序
        filtered_logs.sort(key=lambda x: (x.get('value_score', 0) * 0.6 + x.get('score', 0) * 0.4), reverse=True)
        
        return filtered_logs[:8]  # 限制最多8条

    def _calculate_information_value(self, content: str, log_level: str, error_codes: List[str], services: List[str]) -> float:
        """
        计算日志信息价值分数
        """
        value_score = 0.0
        
        # 日志级别权重
        level_weights = {'FATAL': 1.0, 'ERROR': 0.8, 'WARN': 0.6, 'INFO': 0.4, 'DEBUG': 0.2}
        value_score += level_weights.get(log_level, 0.1)
        
        # 错误码权重
        if error_codes:
            value_score += 0.3
        
        # 服务名称权重
        if services:
            value_score += 0.2
        
        # 内容长度权重（避免过短或过长的日志）
        content_length = len(content)
        if 50 <= content_length <= 500:
            value_score += 0.1
        
        return min(value_score, 1.0)  # 限制最大值为1.0

    def _format_log_entry(self, log: Dict, index: int, match_type: str) -> str:
        """
        格式化日志条目
        """
        content = log.get('content', '')
        score = log.get('score', 0)
        log_level = log.get('log_level', 'UNKNOWN')
        error_codes = log.get('error_codes', [])
        services = log.get('services', [])
        
        formatted_entry = f"#### 日志 {index} ({match_type}, 相关性: {score:.3f})\n"
        formatted_entry += f"**级别**: {log_level}\n"
        
        if error_codes:
            formatted_entry += f"**错误码**: {', '.join(error_codes)}\n"
        if services:
            formatted_entry += f"**涉及服务**: {', '.join(services)}\n"
        
        formatted_entry += f"**内容**: {content}\n\n"
        
        return formatted_entry

    def _build_domain_context(self, context) -> str:
        """
        构建领域知识上下文，为AI提供专业的故障诊断知识
        """
        # 处理不同类型的context
        if isinstance(context, str):
            # 如果是字符串，直接返回基础领域知识
            return "## 领域知识\n基于系统故障诊断的专业知识。"
        
        if not context or not isinstance(context, (list, dict)):
            return "## 领域知识\n暂无相关日志信息。"
        
        # 如果是字典，尝试获取logs
        if isinstance(context, dict):
            logs = context.get('logs', [])
            if not logs:
                return "## 领域知识\n基于系统故障诊断的专业知识。"
        else:
            logs = context
        
        # 提取所有错误码和服务
        error_codes = set()
        services = set()
        
        for log in logs:
            if isinstance(log, dict):
                content = log.get('content', '')
            else:
                content = str(log)
            error_codes.update(self._extract_error_codes(content))
            services.update(self._extract_services(content))
        
        # 构建领域知识上下文
        domain_context = "## 相关错误码的专业知识\n"
        
        for error_code in list(error_codes)[:10]:  # 限制最多10个错误码
            meaning = get_error_code_meaning(error_code)
            category = get_fault_category(error_code)
            severity = get_severity_level(error_code)
            
            domain_context += f"- **{error_code}**: {meaning}\n"
            domain_context += f"  - 分类: {category}\n"
            domain_context += f"  - 严重程度: {severity}\n"
        
        # 添加服务依赖关系
        if services:
            domain_context += "\n## 服务依赖关系\n"
            for service in list(services)[:5]:  # 限制最多5个服务
                dependencies = get_service_dependencies(service)
                if dependencies:
                    domain_context += f"- **{service}** 依赖: {', '.join(dependencies)}\n"
        
        # 添加常见故障模式
        domain_context += "\n## 常见故障模式\n"
        for pattern_name, pattern_info in list(COMMON_PATTERNS.items())[:3]:  # 限制最多3个模式
            domain_context += f"- **{pattern_name}**:\n"
            domain_context += f"  - 症状: {', '.join(pattern_info.get('symptoms', [])[:3])}\n"
            domain_context += f"  - 常见原因: {', '.join(pattern_info.get('root_causes', [])[:3])}\n"
            domain_context += f"  - 立即行动: {', '.join(pattern_info.get('immediate_actions', [])[:2])}\n"
        
        # 添加专家洞察和行业标准
        domain_context += "\n## 专家洞察和行业标准\n"
        expert_patterns = ["数据库连接池耗尽", "认证失败", "支付异常"]
        for pattern in expert_patterns[:2]:  # 限制最多2个模式
            insights = get_expert_insights(pattern)
            standards = get_industry_standards(pattern)
            
            if insights:
                domain_context += f"- **{pattern}专家洞察**:\n"
                for insight in insights[:2]:  # 限制最多2条洞察
                    domain_context += f"  - {insight}\n"
            
            if standards:
                domain_context += f"- **{pattern}行业标准**:\n"
                for standard in standards[:2]:  # 限制最多2条标准
                    domain_context += f"  - {standard}\n"
        
        # 添加行业最佳实践
        domain_context += "\n## 行业最佳实践\n"
        best_practices = get_best_practices("微服务架构")
        if best_practices:
            domain_context += "- **微服务架构最佳实践**:\n"
            for category, practices in list(best_practices.items())[:2]:  # 限制最多2个类别
                domain_context += f"  - {category}: {', '.join(practices[:2])}\n"
        
        return domain_context

    def _extract_log_level(self, content: str) -> str:
        """提取日志级别"""
        import re
        levels = ['FATAL', 'ERROR', 'WARN', 'WARNING', 'INFO', 'INFORMATION', 'DEBUG']
        for level in levels:
            if re.search(r'\b' + level + r'\b', content, re.IGNORECASE):
                return level
        return "UNKNOWN"

    def _extract_error_codes(self, content: str) -> List[str]:
        """提取错误码"""
        import re
        # 匹配大写字母+数字+下划线的模式
        pattern = r'\b[A-Z][A-Z0-9_]{2,}\b'
        matches = re.findall(pattern, content)
        # 过滤掉常见的非错误码词汇
        exclude_words = {'HTTP', 'URL', 'API', 'JSON', 'XML', 'SQL', 'TCP', 'UDP', 'IP', 'DNS'}
        return [match for match in matches if match not in exclude_words]

    def _extract_services(self, content: str) -> List[str]:
        """提取服务名称"""
        import re
        # 匹配以Service结尾的词汇
        pattern = r'\b[A-Za-z][A-Za-z0-9]*Service\b'
        return re.findall(pattern, content)

        # 执行查询

    def query(self, query: str) -> Dict:
        log_results = self.retrieve_logs(query)
        response = self.generate_response(query, log_results)  # 生成响应

        return {
            "response": response,
            "retrieval_stats": len(log_results)
        }

    def _build_follow_up_prompt(self, query: str, context: Dict) -> List[Dict]:
        """构建跟进问题Prompt（返回Markdown格式）"""
        # 构建领域知识上下文
        domain_context = self._build_domain_context(context)
        
        # 构建日志上下文
        log_context = self._build_structured_context(context.get('logs', []))
        
        system_message = SystemMessagePromptTemplate.from_template(f"""
你是一位资深的系统故障诊断专家，具有15年以上的故障排查和系统运维经验。用户正在跟进之前的故障分析，请基于之前的分析结果和当前问题，提供详细、专业的回答。

## 领域知识背景
{domain_context}

## 回答要求
请用Markdown格式回答用户的问题，确保：
- 直接回答用户的具体问题
- 提供技术细节和实用建议
- 保持专业深度和行业经验
- 不要重复之前的分析内容
- 使用清晰的Markdown格式

**重要**: 直接输出Markdown内容，不要重复之前的分析内容。
        """)

        user_message = HumanMessagePromptTemplate.from_template("""
## 相关日志信息
{log_context}

## 用户问题
{query}

请基于以上信息，详细回答用户的问题。注意：这是一个跟进问题，请直接回答用户的具体问题，不要重复之前的分析内容。
        """)

        prompt = ChatPromptTemplate.from_messages([
            system_message,
            user_message
        ])

        return prompt.format_prompt(
            log_context=log_context,
            query=query
        ).to_messages()

    def _build_prevention_prompt(self, query: str, context: Dict) -> List[Dict]:
        """构建预防措施Prompt（返回Markdown格式）"""
        # 构建领域知识上下文
        domain_context = self._build_domain_context(context)
        
        # 构建日志上下文
        log_context = self._build_structured_context(context.get('logs', []))
        
        system_message = SystemMessagePromptTemplate.from_template(f"""
你是一位资深的系统运维专家，具有15年以上的系统架构设计和运维经验。用户询问如何预防系统故障，请提供详细、系统性的预防措施建议。

## 领域知识背景
{domain_context}

## 回答要求
请用Markdown格式回答，确保内容：

### 🛡️ 预防措施分类
- **监控预防**: 实时监控、告警机制、性能指标
- **配置预防**: 系统配置、环境配置、安全配置
- **代码预防**: 代码质量、异常处理、防御性编程
- **流程预防**: 发布流程、测试流程、回滚机制
- **架构预防**: 系统架构、容错设计、降级策略

### 📋 内容要求
- **具体实施**: 提供具体、可操作的实施步骤
- **最佳实践**: 分享行业最佳实践和成功案例
- **工具推荐**: 推荐相关的工具和技术栈
- **优先级排序**: 按重要性和紧急程度排序
- **成本效益**: 考虑实施成本和预期效果

### 📝 格式要求
- 使用Markdown格式组织内容
- 使用表格、列表、代码块等增强可读性
- 使用emoji图标突出重点信息
- 保持结构清晰，层次分明

### 🎯 回答策略
- 基于用户的具体问题提供针对性建议
- 结合系统特点和业务需求
- 提供分阶段的实施计划
- 包含风险评估和应对措施

**重要**: 不要使用JSON格式，直接输出Markdown内容。
        """)

        user_message = HumanMessagePromptTemplate.from_template("""
## 相关日志信息
{log_context}

## 用户问题
{query}

请基于以上信息，提供详细的预防措施建议。
        """)

        prompt = ChatPromptTemplate.from_messages([
            system_message,
            user_message
        ])

        return prompt.format_prompt(
            log_context=log_context,
            query=query
        ).to_messages()

    def _build_dependency_prompt(self, query: str, context: Dict) -> List[Dict]:
        """构建依赖关系Prompt（返回Markdown格式）"""
        # 构建领域知识上下文
        domain_context = self._build_domain_context(context)
        
        # 构建日志上下文
        log_context = self._build_structured_context(context.get('logs', []))
        
        system_message = SystemMessagePromptTemplate.from_template(f"""
你是一位资深的系统架构专家，具有15年以上的微服务架构设计和分布式系统经验。用户询问服务依赖关系，请提供详细、专业的依赖关系分析。

## 领域知识背景
{domain_context}

## 回答要求
请用Markdown格式回答，确保内容：

### 🔗 依赖关系分析
- **服务依赖图**: 清晰展示服务间的依赖关系
- **调用链分析**: 详细分析请求调用链路和数据流
- **依赖类型**: 区分同步依赖、异步依赖、数据依赖等
- **依赖强度**: 评估依赖的紧耦合程度和重要性
- **循环依赖**: 识别和解决潜在的循环依赖问题

### 📊 架构分析
- **系统边界**: 明确各服务的职责边界
- **接口设计**: 分析服务间接口的设计合理性
- **数据一致性**: 分析分布式数据一致性策略
- **故障传播**: 分析故障在依赖链中的传播路径
- **性能瓶颈**: 识别依赖链中的性能瓶颈点

### 🛠️ 优化建议
- **解耦策略**: 提供减少依赖耦合的具体方案
- **容错设计**: 建议容错和降级策略
- **监控方案**: 提供依赖关系的监控和告警方案
- **重构建议**: 基于依赖分析提供架构重构建议

### 📝 格式要求
- 使用Markdown格式组织内容
- 使用表格、列表、代码块等增强可读性
- 使用emoji图标突出重点信息
- 保持结构清晰，层次分明

**重要**: 不要使用JSON格式，直接输出Markdown内容。
        """)

        user_message = HumanMessagePromptTemplate.from_template("""
## 相关日志信息
{log_context}

## 用户问题
{query}

请基于以上信息，分析服务依赖关系。
        """)

        prompt = ChatPromptTemplate.from_messages([
            system_message,
            user_message
        ])

        return prompt.format_prompt(
            log_context=log_context,
            query=query
        ).to_messages()

    def _build_explanation_prompt(self, query: str, context: Dict) -> List[Dict]:
        """构建解释请求Prompt（返回Markdown格式）"""
        # 构建领域知识上下文
        domain_context = self._build_domain_context(context)
        
        # 构建日志上下文
        log_context = self._build_structured_context(context.get('logs', []))
        
        system_message = SystemMessagePromptTemplate.from_template(f"""
你是一位资深的系统专家，具有15年以上的技术架构和系统设计经验。用户请求解释某个概念或现象，请提供详细、易懂、专业的解释。

## 领域知识背景
{domain_context}

## 回答要求
请用Markdown格式回答，确保内容：

### 📚 解释内容
- **概念定义**: 清晰、准确的概念定义
- **工作原理**: 详细的工作原理和机制说明
- **实际应用**: 在系统中的实际应用场景
- **相关示例**: 提供具体的代码示例或配置示例
- **注意事项**: 使用时需要注意的问题和限制

### 🎯 解释策略
- **层次递进**: 从基础概念到高级应用
- **图文并茂**: 使用图表、代码块等增强理解
- **对比分析**: 与其他相关概念进行对比
- **最佳实践**: 分享相关的最佳实践
- **常见问题**: 解答相关的常见问题

### 📝 格式要求
- 使用Markdown格式组织内容
- 使用标题、列表、代码块等增强可读性
- 使用emoji图标突出重点信息
- 保持结构清晰，层次分明
- 使用表格对比不同方案

### 🔍 深度要求
- 提供技术细节和实现原理
- 包含相关的技术标准和规范
- 分享行业经验和教训
- 提供进一步学习的方向

**重要**: 不要使用JSON格式，直接输出Markdown内容。
        """)

        user_message = HumanMessagePromptTemplate.from_template("""
## 相关日志信息
{log_context}

## 用户问题
{query}

请基于以上信息，详细解释用户的问题。
        """)

        prompt = ChatPromptTemplate.from_messages([
            system_message,
            user_message
        ])

        return prompt.format_prompt(
            log_context=log_context,
            query=query
        ).to_messages()

    def _build_general_prompt(self, query: str, context: Dict) -> List[Dict]:
        """构建一般问题Prompt（返回Markdown格式）"""
        # 构建领域知识上下文
        domain_context = self._build_domain_context(context)
        
        # 构建日志上下文
        log_context = self._build_structured_context(context.get('logs', []))
        
        system_message = SystemMessagePromptTemplate.from_template(f"""
你是一位资深的系统专家，具有15年以上的技术经验和丰富的行业知识。用户提出了一个一般性问题，请提供友好、详细、专业的回答。

## 领域知识背景
{domain_context}

## 回答要求
请用Markdown格式回答，确保内容：

### 🤝 回答风格
- **友好亲切**: 使用友好、耐心的语调
- **专业准确**: 提供准确、专业的技术信息
- **详细全面**: 给出详细、全面的回答
- **易于理解**: 使用通俗易懂的语言

### 📋 内容要求
- **直接回答**: 直接、明确地回答用户的问题
- **背景信息**: 提供相关的背景信息和上下文
- **实用建议**: 给出实用的建议和指导
- **相关资源**: 提供相关的学习资源和参考资料
- **扩展知识**: 适当扩展相关的知识点

### 📝 格式要求
- 使用Markdown格式组织内容
- 使用标题、列表、代码块等增强可读性
- 使用emoji图标增加亲和力
- 保持结构清晰，层次分明

### 🎯 回答策略
- 如果问题涉及技术概念，提供清晰的定义和解释
- 如果问题涉及操作步骤，提供详细的步骤说明
- 如果问题涉及最佳实践，分享行业经验和建议
- 如果问题涉及工具选择，提供对比分析和推荐

**重要**: 不要使用JSON格式，直接输出Markdown内容。
        """)

        user_message = HumanMessagePromptTemplate.from_template("""
## 相关日志信息
{log_context}

## 用户问题
{query}

请基于以上信息，回答用户的问题。
        """)

        prompt = ChatPromptTemplate.from_messages([
            system_message,
            user_message
        ])

        return prompt.format_prompt(
            log_context=log_context,
            query=query
        ).to_messages()

    # 示例使用


if __name__ == "__main__":
    # 初始化系统
    system = TopKLogSystem(
        log_path="./data/log",
        llm="deepseek-r1:7b",
        embedding_model="bge-large:latest"
    )

    # 执行查询
    query = "如何解决数据库连接池耗尽的问题？"
    result = system.query(query)

    print("查询:", query)
    print("响应:", result["response"])
    print("检索统计:", result["retrieval_stats"])
