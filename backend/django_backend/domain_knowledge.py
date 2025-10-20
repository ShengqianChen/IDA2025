#!/usr/bin/env python3
"""
领域知识配置文件
包含电商系统的错误码、服务依赖关系、故障模式等专业知识
"""

# 基于互联网专家知识和行业最佳实践的增强版错误码分类
ERROR_CODE_MEANINGS = {
    # 认证相关
    "INVALID_TOKEN": "Token校验失败，通常由JWT签名算法不匹配或密钥验证失败导致",
    "MFA_FAIL": "多因子认证失败，验证码错误或设备不匹配",
    "OAUTH_FAIL": "OAuth授权失败，授权码失效或平台配置错误",
    "SESSION_FIXATE": "会话固定攻击检测，需要重置session",
    "BRUTE_FORCE": "暴力破解攻击检测，需要启用验证码或锁定账户",
    "PASSWORD_EXPIRE": "密码即将过期，需要提醒用户更新",
    "WEAK_PASSWORD_LIST": "密码强度不足，包含常见弱密码",
    
    # 支付相关
    "PAY_CHANNEL_SWITCH": "支付渠道切换，原渠道故障自动切换",
    "PAY_FEE_CHANGE": "支付手续费变更，渠道调整费率",
    "PAY_RISK": "支付风险检测，异常大额支付或可疑行为",
    "PAY_SIGN_REPEAT": "支付签名重复，可能存在重放攻击",
    "SETTLE_FAIL": "结算失败，对账不平或渠道问题",
    "REFUND_FEE_MISSING": "退款手续费缺失，配置错误",
    
    # 数据库相关
    "DB_CONNECTION_LOST": "数据库连接池耗尽，无法获取连接",
    "DB_REPLICA_LAG": "数据库主从同步延迟，可能影响数据一致性",
    "MASTER_SLAVE_DESYNC": "主从数据库不同步，需要检查复制状态",
    
    # 库存相关
    "STOCK_EXPIRE": "库存过期，商品超过保质期",
    "STOCK_NEGATIVE": "库存为负，系统库存与实际不符",
    "STOCK_LESS": "库存少货，实际比系统少",
    "STOCK_FREEZE": "库存冻结失败，冻结记录冲突",
    "BATCH_STOCK_FAIL": "批量扣减失败，中间件网络闪断",
    
    # 订单相关
    "ORDER_DOUBLE": "重复订单，同一秒提交多次",
    "ORDER_TIMEOUT": "订单创建超时，下游服务响应慢",
    "ORDER_REFUND_DOUBLE": "重复退款，已退金额超应付",
    "ORDER_STATUS_LAG": "订单状态滞后，与物流状态不同步",
    
    # 系统资源相关
    "THREAD_STACK_HIGH": "线程栈使用过高，递归深度超限",
    "MEMORY_SWAP_HIGH": "交换分区使用过高，内存耗尽",
    "HEAP_ALLOCATION_FAIL": "堆分配失败，内存不足",
    "DISK_TEMP_HIGH": "磁盘温度过高，散热故障",
    "CACHE_VALUE_COMPRESSION_FAIL": "缓存压缩失败，内存不足",
    
    # 网络相关
    "BACKEND_HEALTH_FAIL": "后端健康检查失败，服务返回503状态",
    "BACKEND_CONN_DROP": "后端连接断开，网络不稳定",
    "DNS_FAIL": "DNS解析失败，域名配置错误",
    "SSL_HANDSHAKE_FAIL": "SSL握手失败，证书问题",
    
    # 日志相关
    "CORRUPTED_LOG": "日志文件损坏，磁盘写入过程中断电",
    "LOG_ENCODING_ERR": "日志编码错误，非UTF-8字符",
    "LOG_TAMPER": "日志被篡改，校验失败",
    "LOG_BUFFER_FULL": "日志缓冲区满，瞬时峰值",
    
    # 缓存相关
    "CACHE_HIT_DROP": "缓存命中率下降，性能问题",
    "CACHE_REHASH_SLOW": "缓存重哈希慢，负载过高",
    "CACHE_TTL_MISS": "缓存TTL缺失，配置错误",
    
    # 消息队列相关
    "KAFKA_LAG_50W": "Kafka消费延迟50万条，消费者卡死",
    "MESSAGE_IN_FLIGHT_HIGH": "在途消息过多，消费者处理能力不足",
    "MESSAGE_BROKER_OOM": "消息代理内存溢出，需要扩容",
    
    # 文件相关
    "FILE_QUARANTINE": "文件被隔离，安全扫描发现威胁",
    "UPLOAD_FILE_LOCK": "上传文件被锁定，并发冲突",
    "FILE_SIZE_ZERO": "文件大小为0，上传失败",
    
    # 证书相关
    "CERT_EXPIRE_7D": "证书7天后过期，需要续期",
    "CERT_PRIVATE_KEY_LOST": "证书私钥丢失，需要重新生成",
    "CERT_REVOKED": "证书被撤销，需要更新证书",
    
    # 配置相关
    "CONFIG_JSON_INVALID": "配置文件JSON格式错误",
    "ROUTE_REDIRECT_LOOP": "路由重定向循环，配置错误",
    "API_VERSION_UNSUPPORTED": "API版本不支持，需要升级",
}

# 服务依赖关系
SERVICE_DEPENDENCIES = {
    "AuthService": ["DatabaseService", "CacheService", "NotificationService"],
    "OrderService": ["AuthService", "PaymentService", "StockService", "NotificationService"],
    "PaymentService": ["AuthService", "DatabaseService", "NotificationService"],
    "StockService": ["DatabaseService", "CacheService", "NotificationService"],
    "UserService": ["AuthService", "DatabaseService", "NotificationService"],
    "CartService": ["AuthService", "StockService", "DatabaseService"],
    "SearchService": ["DatabaseService", "CacheService"],
    "GatewayService": ["AuthService", "OrderService", "PaymentService", "StockService"],
    "LogService": ["DatabaseService", "FileSystemService"],
    "NotiService": ["AuthService", "DatabaseService", "SMSService", "EmailService"],
    "EmailService": ["AuthService", "DatabaseService", "TemplateService"],
}

# 故障分类和严重程度
FAULT_CATEGORIES = {
    "AUTHENTICATION": {
        "description": "认证和授权相关故障",
        "severity_mapping": {
            "INVALID_TOKEN": "HIGH",
            "MFA_FAIL": "MEDIUM", 
            "BRUTE_FORCE": "HIGH",
            "SESSION_FIXATE": "HIGH",
            "OAUTH_FAIL": "MEDIUM"
        },
        "common_causes": ["JWT配置错误", "密钥不匹配", "验证码错误", "设备不匹配"],
        "typical_solutions": ["检查JWT配置", "更新密钥", "重置验证码", "检查设备绑定"]
    },
    
    "PAYMENT": {
        "description": "支付相关故障",
        "severity_mapping": {
            "PAY_CHANNEL_SWITCH": "MEDIUM",
            "PAY_RISK": "HIGH",
            "SETTLE_FAIL": "HIGH",
            "PAY_SIGN_REPEAT": "HIGH"
        },
        "common_causes": ["渠道故障", "风控规则触发", "对账不平", "重放攻击"],
        "typical_solutions": ["切换支付渠道", "调整风控规则", "重新对账", "检查签名机制"]
    },
    
    "DATABASE": {
        "description": "数据库相关故障",
        "severity_mapping": {
            "DB_CONNECTION_LOST": "FATAL",
            "DB_REPLICA_LAG": "HIGH",
            "MASTER_SLAVE_DESYNC": "HIGH"
        },
        "common_causes": ["连接池耗尽", "主从延迟", "网络中断", "配置错误"],
        "typical_solutions": ["增加连接池大小", "检查网络", "重启复制", "修复配置"]
    },
    
    "INVENTORY": {
        "description": "库存相关故障",
        "severity_mapping": {
            "STOCK_NEGATIVE": "HIGH",
            "STOCK_EXPIRE": "MEDIUM",
            "STOCK_FREEZE": "MEDIUM",
            "BATCH_STOCK_FAIL": "HIGH"
        },
        "common_causes": ["库存计算错误", "商品过期", "并发冲突", "网络闪断"],
        "typical_solutions": ["重新计算库存", "清理过期商品", "解决并发", "检查网络"]
    },
    
    "SYSTEM_RESOURCE": {
        "description": "系统资源相关故障",
        "severity_mapping": {
            "THREAD_STACK_HIGH": "FATAL",
            "MEMORY_SWAP_HIGH": "HIGH",
            "HEAP_ALLOCATION_FAIL": "FATAL",
            "DISK_TEMP_HIGH": "HIGH"
        },
        "common_causes": ["递归过深", "内存泄漏", "堆溢出", "散热故障"],
        "typical_solutions": ["优化递归", "检查内存泄漏", "增加内存", "改善散热"]
    },
    
    "NETWORK": {
        "description": "网络相关故障",
        "severity_mapping": {
            "BACKEND_HEALTH_FAIL": "HIGH",
            "BACKEND_CONN_DROP": "HIGH",
            "DNS_FAIL": "HIGH",
            "SSL_HANDSHAKE_FAIL": "HIGH"
        },
        "common_causes": ["服务宕机", "网络中断", "DNS错误", "证书问题"],
        "typical_solutions": ["重启服务", "检查网络", "修复DNS", "更新证书"]
    }
}

# 常见故障模式和解决方案
COMMON_PATTERNS = {
    "连接池耗尽": {
        "symptoms": ["DB_CONNECTION_LOST", "连接超时", "无法获取连接"],
        "root_causes": ["连接泄漏", "连接数配置过小", "长时间事务"],
        "immediate_actions": ["重启服务", "增加连接池大小", "检查连接泄漏"],
        "long_term_fixes": ["优化连接管理", "调整连接池配置", "代码审查"],
        "prevention": ["连接池监控", "定期检查", "代码规范"]
    },
    
    "认证失败": {
        "symptoms": ["INVALID_TOKEN", "MFA_FAIL", "OAUTH_FAIL"],
        "root_causes": ["JWT配置错误", "密钥不匹配", "验证码错误"],
        "immediate_actions": ["检查JWT配置", "更新密钥", "重置验证码"],
        "long_term_fixes": ["统一认证配置", "密钥轮换机制", "多因子认证"],
        "prevention": ["配置管理", "密钥管理", "安全审计"]
    },
    
    "库存不一致": {
        "symptoms": ["STOCK_NEGATIVE", "STOCK_LESS", "STOCK_DIFF"],
        "root_causes": ["并发冲突", "计算错误", "数据同步问题"],
        "immediate_actions": ["重新计算库存", "锁定库存操作", "检查数据"],
        "long_term_fixes": ["优化并发控制", "改进计算逻辑", "数据同步"],
        "prevention": ["库存监控", "定期盘点", "并发测试"]
    },
    
    "支付异常": {
        "symptoms": ["PAY_RISK", "SETTLE_FAIL", "PAY_SIGN_REPEAT"],
        "root_causes": ["风控规则", "对账不平", "重放攻击"],
        "immediate_actions": ["调整风控", "重新对账", "检查签名"],
        "long_term_fixes": ["优化风控", "改进对账", "防重放机制"],
        "prevention": ["风控监控", "对账监控", "安全审计"]
    }
}

# 监控建议
MONITORING_RECOMMENDATIONS = {
    "AUTHENTICATION": [
        "监控认证失败率",
        "监控JWT过期情况", 
        "监控异常登录行为",
        "监控多因子认证成功率"
    ],
    "PAYMENT": [
        "监控支付成功率",
        "监控支付渠道健康状态",
        "监控风控规则触发情况",
        "监控对账差异"
    ],
    "DATABASE": [
        "监控数据库连接数",
        "监控主从同步延迟",
        "监控慢查询",
        "监控数据库性能指标"
    ],
    "INVENTORY": [
        "监控库存变化",
        "监控库存异常",
        "监控库存操作延迟",
        "监控库存一致性"
    ],
    "SYSTEM_RESOURCE": [
        "监控内存使用率",
        "监控CPU使用率",
        "监控磁盘空间",
        "监控网络延迟"
    ],
    "NETWORK": [
        "监控服务健康状态",
        "监控网络连接",
        "监控DNS解析",
        "监控SSL证书状态"
    ]
}

def get_error_code_meaning(error_code: str) -> str:
    """获取错误码含义"""
    return ERROR_CODE_MEANINGS.get(error_code, f"未知错误码: {error_code}")

def get_service_dependencies(service_name: str) -> list:
    """获取服务依赖关系"""
    return SERVICE_DEPENDENCIES.get(service_name, [])

def get_fault_category(error_code: str) -> str:
    """根据错误码获取故障分类"""
    for category, info in FAULT_CATEGORIES.items():
        if error_code in info["severity_mapping"]:
            return category
    return "UNKNOWN"

def get_severity_level(error_code: str) -> str:
    """获取错误码的严重程度"""
    for category, info in FAULT_CATEGORIES.items():
        if error_code in info["severity_mapping"]:
            return info["severity_mapping"][error_code]
    return "UNKNOWN"

def get_common_pattern_info(pattern_name: str) -> dict:
    """获取常见故障模式信息"""
    return COMMON_PATTERNS.get(pattern_name, {})

def get_monitoring_recommendations(category: str) -> list:
    """获取监控建议"""
    return MONITORING_RECOMMENDATIONS.get(category, [])

# 基于互联网专家知识的增强故障模式
EXPERT_ENHANCED_PATTERNS = {
    "数据库连接池耗尽": {
        "expert_insights": [
            "根据AWS和Google Cloud的最佳实践，连接池大小应设置为CPU核心数的2-4倍",
            "连接泄漏是导致池耗尽的主要原因，建议使用连接池监控工具",
            "长时间运行的事务会占用连接，建议设置事务超时时间"
        ],
        "industry_standards": [
            "HikariCP推荐最大连接数不超过200",
            "MySQL官方建议最大连接数不超过1000",
            "PostgreSQL推荐连接数不超过100"
        ],
        "monitoring_metrics": [
            "活跃连接数",
            "连接等待时间", 
            "连接获取失败率",
            "连接池使用率"
        ]
    },
    
    "认证失败": {
        "expert_insights": [
            "JWT令牌过期是认证失败的主要原因，建议设置合理的过期时间",
            "多因子认证失败通常由时间同步问题导致，建议使用NTP同步",
            "OAuth授权失败多由重定向URI不匹配引起"
        ],
        "security_best_practices": [
            "实施零信任安全模型",
            "使用强密码策略和密码轮换",
            "启用审计日志记录所有认证事件",
            "实施账户锁定机制防止暴力破解"
        ],
        "compliance_requirements": [
            "GDPR要求用户数据保护",
            "PCI DSS要求支付数据安全",
            "SOX要求审计跟踪"
        ]
    },
    
    "支付异常": {
        "expert_insights": [
            "支付风控系统应基于机器学习和规则引擎",
            "重复支付检测需要基于订单ID和时间窗口",
            "支付渠道故障应自动切换到备用渠道"
        ],
        "financial_compliance": [
            "PCI DSS Level 1认证要求",
            "反洗钱(AML)监控要求",
            "KYC(了解你的客户)验证要求"
        ],
        "risk_management": [
            "实时风险评估",
            "异常交易检测",
            "欺诈模式识别",
            "风险评分模型"
        ]
    }
}

# 行业最佳实践
INDUSTRY_BEST_PRACTICES = {
    "微服务架构": {
        "故障隔离": [
            "使用断路器模式防止级联故障",
            "实施超时和重试机制",
            "使用熔断器保护下游服务"
        ],
        "监控和可观测性": [
            "实施分布式链路追踪",
            "使用指标监控(如Prometheus)",
            "集中化日志管理(如ELK Stack)"
        ],
        "服务发现": [
            "使用服务注册中心",
            "实施健康检查机制",
            "支持服务版本管理"
        ]
    },
    
    "数据库管理": {
        "连接管理": [
            "使用连接池管理数据库连接",
            "实施读写分离",
            "使用数据库代理"
        ],
        "性能优化": [
            "定期分析慢查询",
            "优化索引策略",
            "使用查询缓存"
        ],
        "高可用性": [
            "实施主从复制",
            "使用数据库集群",
            "实施自动故障转移"
        ]
    },
    
    "安全最佳实践": {
        "认证授权": [
            "实施多因子认证",
            "使用OAuth 2.0和OpenID Connect",
            "实施基于角色的访问控制(RBAC)"
        ],
        "数据保护": [
            "数据加密传输和存储",
            "实施数据脱敏",
            "定期安全审计"
        ],
        "威胁防护": [
            "实施Web应用防火墙",
            "使用入侵检测系统",
            "定期漏洞扫描"
        ]
    }
}

def get_expert_insights(pattern_name: str) -> list:
    """获取专家洞察"""
    return EXPERT_ENHANCED_PATTERNS.get(pattern_name, {}).get("expert_insights", [])

def get_industry_standards(pattern_name: str) -> list:
    """获取行业标准"""
    return EXPERT_ENHANCED_PATTERNS.get(pattern_name, {}).get("industry_standards", [])

def get_best_practices(category: str) -> dict:
    """获取最佳实践"""
    return INDUSTRY_BEST_PRACTICES.get(category, {})
