import os

# chroma 不上传数据
os.environ["ANONYMIZED_TELEMETRY"] = "false"
os.environ["DISABLE_TELEMETRY"] = "1"
os.environ["CHROMA_TELEMETRY_ENABLED"] = "false"

import json
import logging
import pandas as pd
from typing import Any, Dict, List

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

            # LLM 生成响应

    def generate_response(self, query: str, context: Dict) -> str:
        prompt = self._build_prompt(query, context)  # 构建提示词

        try:
            response = self.llm.invoke(prompt)  # 调用LLM
            return response
        except Exception as e:
            logger.error(f"LLM调用失败: {e}")
            return f"生成响应时出错: {str(e)}"

            # 构建 prompt

    def _build_prompt(self, query: str, context: Dict) -> List[Dict]:
        # 构建领域知识上下文
        domain_context = self._build_domain_context(context)
        
        # 系统消息 - 定义专业角色和分析框架
        system_message = SystemMessagePromptTemplate.from_template(f"""
你是一位资深的电商系统故障诊断专家，具有丰富的日志分析和故障排查经验。你的任务是基于提供的日志信息，进行专业的故障分析。

## 领域知识背景
{domain_context}

## 分析框架
请按照以下三个步骤进行结构化分析：

### 第一步：故障现象识别
- 识别日志中的错误级别（FATAL/ERROR/WARN/INFO）
- 提取关键错误码和服务名称，结合领域知识理解其含义
- 分析故障发生的时间模式和频率
- 评估故障的严重程度和影响范围

### 第二步：根因分析
- 基于错误码和日志内容分析可能的根本原因
- 考虑服务间的依赖关系和调用链
- 识别触发故障的条件和环境因素
- 结合常见故障模式提供置信度评估（高/中/低）

### 第三步：解决方案建议
- 提供立即修复措施（紧急处理）
- 建议长期优化方案（根本解决）
- 给出预防措施和监控建议
- 按优先级排序解决方案

## 输出格式要求
请严格按照以下JSON格式输出分析结果，确保结构完整：

JSON格式要求：
- fault_summary: 包含severity("HIGH"/"MEDIUM"/"LOW")、category("AUTHENTICATION"/"PAYMENT"/"DATABASE"/"INVENTORY"/"SYSTEM_RESOURCE"/"NETWORK")、description(字符串)、affected_services(字符串数组)、error_codes(字符串数组)
- root_cause_analysis: 包含primary_cause(字符串)、contributing_factors(字符串数组)、confidence_level("HIGH"/"MEDIUM"/"LOW")、reasoning(字符串)
- solutions: 包含immediate_actions(对象数组)、long_term_fixes(对象数组)、prevention_measures(对象数组)
- monitoring_recommendations: 字符串数组

每个解决方案对象必须包含action(字符串)和priority("HIGH"/"MEDIUM"/"LOW")字段。

重要：直接输出JSON内容，不要包含任何markdown代码块标记、解释文字或其他格式。
        """)

        # 构建结构化的日志上下文
        log_context = self._build_structured_context(context)

        # 用户消息 - 明确分析任务
        user_message = HumanMessagePromptTemplate.from_template("""
## 相关日志信息
{log_context}

## 分析任务
用户问题：{query}

请基于以上日志信息，按照分析框架进行专业的故障诊断分析。

输出要求：
1. 直接输出JSON格式的分析结果
2. 不要包含任何markdown代码块标记（如```json）
3. 不要包含任何解释文字或额外内容
4. 确保JSON格式完全正确，可以被直接解析
        """)

        # 创建提示词
        prompt = ChatPromptTemplate.from_messages([
            system_message,
            user_message
        ])

        return prompt.format_prompt(
            log_context=log_context,
            query=query
        ).to_messages()

    def _build_structured_context(self, context: List[Dict]) -> str:
        """
        构建智能化的日志上下文，提高信息利用效率
        """
        if not context:
            return "未找到相关日志信息。"
        
        # 智能过滤和排序
        filtered_context = self._intelligent_context_filter(context)
        
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

    def _build_domain_context(self, context: List[Dict]) -> str:
        """
        构建领域知识上下文，为AI提供专业的故障诊断知识
        """
        if not context:
            return "未找到相关日志信息。"
        
        # 提取所有错误码和服务
        error_codes = set()
        services = set()
        
        for log in context:
            content = log.get('content', '')
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
