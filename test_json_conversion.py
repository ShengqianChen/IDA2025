#!/usr/bin/env python3
"""
测试JSON到Markdown转换功能
"""
import json
import re

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

if __name__ == "__main__":
    # 测试实际AI响应（包含Markdown代码块标记）
    test_json = '''```json
{
  "fault_summary": {
    "severity": "LOW",
    "category": "SYSTEM_RESOURCE",
    "description": "反序列化类不存在导致的缓存问题",
    "affected_services": ["Alatest93"],
    "error_codes": ["ERROR", "CACHE_DESERIALIZE_FAIL"]
  },
  "root_cause_analysis": {
    "primary_cause": "反序列化类不存在",
    "contributing_factors": [
      "缓存配置问题",
      "类路径错误"
    ],
    "confidence_level": "HIGH",
    "reasoning": "日志明确显示反序列化类不存在，这是典型的配置问题。"
  },
  "solutions": {
    "immediate_actions": [
      {
        "action": "检查反序列化类路径配置",
        "priority": "HIGH"
      }
    ],
    "long_term_fixes": [
      {
        "action": "优化缓存配置",
        "priority": "MEDIUM"
      }
    ],
    "prevention_measures": [
      {
        "action": "增加缓存监控",
        "priority": "LOW"
      }
    ]
  },
  "monitoring_recommendations": ["监控缓存反序列化成功率"]
}
```'''
    
    print("原始JSON:")
    print(test_json)
    print("\n" + "="*50 + "\n")
    
    result = json_to_markdown(test_json)
    print("转换后的Markdown:")
    print(result)
