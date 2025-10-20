#!/usr/bin/env python3
"""
验证修复：测试_extract_log_level方法
"""

def test_extract_log_level():
    """测试日志级别提取方法"""
    import re
    
    def _extract_log_level(content: str) -> str:
        """提取日志级别"""
        levels = ['FATAL', 'ERROR', 'WARN', 'WARNING', 'INFO', 'INFORMATION', 'DEBUG']
        for level in levels:
            if re.search(r'\b' + level + r'\b', content, re.IGNORECASE):
                return level
        return "UNKNOWN"
    
    # 测试用例
    test_cases = [
        "2024-01-01 ERROR: Database connection failed",
        "FATAL: System crash detected",
        "WARN: High memory usage",
        "INFO: User login successful",
        "DEBUG: Processing request"
    ]
    
    print("测试日志级别提取:")
    for test_case in test_cases:
        level = _extract_log_level(test_case)
        print(f"  '{test_case}' -> {level}")
    
    print("✅ 日志级别提取测试完成")

if __name__ == "__main__":
    test_extract_log_level()
