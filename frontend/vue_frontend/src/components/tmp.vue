<template>
  <div class="message" :class="{ 'user-message': isUser }">
    <div class="message-avatar">
      <div :class="isUser ? 'user-avatar' : 'bot-avatar'">
        {{ isUser ? '用户' : 'AI' }}
      </div>
    </div>
    <div class="message-content">
      <div class="message-text" v-html="formattedContent"></div>
      <div class="message-time">
        {{ formatTime(timestamp) }}
      </div>
    </div>
  </div>
</template>

<script setup>
// 组件用途：
// - 展示单条聊天消息（用户/AI 不同气泡与头像样式）
// - 对 AI 回复启用 Markdown 渲染与代码高亮，提升可读性
// - 自动高亮日志文本中的【错误级别 / 服务名称 / 错误码】
// 注意：仅对 AI 消息使用 v-html 渲染（用户消息保持纯文本），以降低 XSS 风险
import { defineProps, computed } from 'vue';
import { marked } from 'marked';
import hljs from 'highlight.js';

const props = defineProps({
  isUser: {
    type: Boolean,
    required: true
  },
  content: {
    type: String,
    required: true
  },
  timestamp: {
    type: Date,
    required: true
  }
});

// 配置 marked：开启 GFM、换行，并结合 highlight.js 实现代码高亮
marked.setOptions({
  highlight: function(code, lang) {
    if (lang && hljs.getLanguage(lang)) {
      try {
        return hljs.highlight(code, { language: lang }).value;
      } catch (err) {}
    }
    try {
      return hljs.highlightAuto(code).value;
    } catch (err) {}
    return code;
  },
  breaks: true,
  gfm: true
});

// 格式化内容：
// - 用户消息：按原文显示（不渲染 HTML）
// - AI 消息：
//   1) 用正则给错误级别/服务名/错误码加语义标签（用于配色高亮）
//   2) 使用 marked 渲染 Markdown + 代码高亮
const formattedContent = computed(() => {
  let processedContent = props.content;
  
  // 如果不是用户消息，进行 Markdown 渲染和日志元素高亮
  if (!props.isUser) {
    // 处理错误级别高亮
    processedContent = processedContent
      .replace(/\b(ERROR|FATAL)\b/g, '<span class="error-level error-fatal">$1</span>')
      .replace(/\b(WARN|WARNING)\b/g, '<span class="error-level error-warn">$1</span>')
      .replace(/\b(INFO|INFORMATION)\b/g, '<span class="error-level error-info">$1</span>')
      .replace(/\b(DEBUG)\b/g, '<span class="error-level error-debug">$1</span>');
    
    // 处理服务名称高亮（可按实际服务清单扩展）
    processedContent = processedContent
      .replace(/\b(AuthService|OrderService|PaymentService|LogService|UserService|CartService|EmailService|GatewayService|SearchService|StockService|NotiService)\b/g, 
               '<span class="service-name">$1</span>');
    
    // 处理错误码高亮（可按实际错误码清单扩展）
    processedContent = processedContent
      .replace(/\b(INVALID_TOKEN|TIMEOUT|DB_CONNECTION_LOST|CORRUPTED_LOG|MFA_FAIL|PAY_FEE_CHANGE|STOCK_EXPIRE|ORDER_SPLIT|SMS_SIGN_FAIL|LOGIN_IP_CHANGE|CART_ITEM_DUPLICATE|LIST_UNSUBSCRIBE|BACKEND_HEALTH_FAIL|LOG_LOST_TIME|QUERY_SUGGEST|PASSWORD_EXPIRE|BALANCE_REFUND_FAIL|PAY_CHANNEL_SWITCH|STOCK_MOVE|ORDER_RECEIPT_FAIL|INBOX_FULL|BIND_PHONE_FAIL|CART_DISCOUNT_EXPIRE|DKIM_FAIL|CACHE_WARM|LOG_ENCODING_ERR|FIELD_MISSING|SSO_LOGIN|PAY_RISK)\b/g, 
               '<span class="error-code">$1</span>');
    
    // 渲染Markdown
    processedContent = marked(processedContent);
  }
  
  return processedContent;
});

const formatTime = (date) => {
  return new Date(date).toLocaleTimeString();
};
</script>

<style scoped>
.message {
  display: flex;
  margin-bottom: 1rem;
  max-width: 80%;
  word-wrap: break-word;
  overflow-wrap: break-word;
}

.message.user-message {
  margin-left: auto;
  flex-direction: row-reverse;
}

.message-avatar {
  margin-right: 0.5rem;
}

.user-message .message-avatar {
  margin-right: 0;
  margin-left: 0.5rem;
}

.user-avatar, .bot-avatar {
  width: 2.5rem;
  height: 2.5rem;
  border-radius: 50%;
  display: flex;
  justify-content: center;
  align-items: center;
  font-weight: bold;
  font-size: 0.875rem;
}

.user-avatar {
  background-color: var(--primary-color);
  color: white;
}

.bot-avatar {
  background-color: var(--secondary-color);
  color: white;
}

.message-content {
  padding: 0.75rem 1rem;
  border-radius: var(--radius);
  position: relative;
}

.message:not(.user-message) .message-content {
  background-color: var(--bot-message);
}

.user-message .message-content {
  background-color: var(--user-message);
}

.message-text {
  margin-bottom: 0.25rem;
  line-height: 1.5;
}

.message-time {
  font-size: 0.75rem;
  color: var(--text-secondary);
  text-align: right;
}

/* Markdown样式 */
.message-text :deep(h1), .message-text :deep(h2), .message-text :deep(h3) {
  margin: 0.5rem 0;
  color: var(--text-primary);
}

.message-text :deep(h1) {
  font-size: 1.25rem;
  border-bottom: 2px solid var(--primary-color);
  padding-bottom: 0.25rem;
}

.message-text :deep(h2) {
  font-size: 1.125rem;
  color: var(--primary-color);
}

.message-text :deep(h3) {
  font-size: 1rem;
  color: var(--text-primary);
}

.message-text :deep(p) {
  margin: 0.5rem 0;
  line-height: 1.6;
}

.message-text :deep(ul), .message-text :deep(ol) {
  margin: 0.5rem 0;
  padding-left: 1.5rem;
}

.message-text :deep(li) {
  margin: 0.25rem 0;
}

.message-text :deep(code) {
  background-color: #f1f5f9;
  padding: 0.125rem 0.25rem;
  border-radius: 4px;
  font-family: 'Courier New', monospace;
  font-size: 0.875rem;
}

.message-text :deep(pre) {
  background-color: #1e293b;
  color: #e2e8f0;
  padding: 1rem;
  border-radius: 8px;
  overflow-x: auto;
  margin: 0.5rem 0;
}

.message-text :deep(pre code) {
  background-color: transparent;
  padding: 0;
  color: inherit;
}

.message-text :deep(blockquote) {
  border-left: 4px solid var(--primary-color);
  padding-left: 1rem;
  margin: 0.5rem 0;
  color: var(--text-secondary);
  font-style: italic;
}

.message-text :deep(table) {
  width: 100%;
  border-collapse: collapse;
  margin: 0.5rem 0;
}

.message-text :deep(th), .message-text :deep(td) {
  border: 1px solid var(--border-color);
  padding: 0.5rem;
  text-align: left;
}

.message-text :deep(th) {
  background-color: var(--bg-color);
  font-weight: 600;
}

/* 错误级别颜色标识 */
.error-level {
  padding: 0.125rem 0.375rem;
  border-radius: 4px;
  font-weight: 600;
  font-size: 0.75rem;
  text-transform: uppercase;
  letter-spacing: 0.025em;
}

.error-fatal {
  background-color: #fef2f2;
  color: #dc2626;
  border: 1px solid #fecaca;
}

.error-warn {
  background-color: #fffbeb;
  color: #d97706;
  border: 1px solid #fed7aa;
}

.error-info {
  background-color: #eff6ff;
  color: #2563eb;
  border: 1px solid #bfdbfe;
}

.error-debug {
  background-color: #f0fdf4;
  color: #16a34a;
  border: 1px solid #bbf7d0;
}

/* 服务名称样式 */
.service-name {
  background-color: #f1f5f9;
  color: var(--primary-color);
  padding: 0.125rem 0.375rem;
  border-radius: 4px;
  font-weight: 500;
  font-size: 0.875rem;
  border: 1px solid #cbd5e1;
}

/* 错误码样式 */
.error-code {
  background-color: #fef3c7;
  color: #92400e;
  padding: 0.125rem 0.375rem;
  border-radius: 4px;
  font-weight: 500;
  font-size: 0.75rem;
  font-family: 'Courier New', monospace;
  border: 1px solid #fde68a;
}

/* 响应式设计 */
@media (max-width: 768px) {
  .message {
    max-width: 95%;
    margin-bottom: 0.75rem;
  }
  
  .message-avatar {
    margin-right: 0.375rem;
  }
  
  .user-message .message-avatar {
    margin-left: 0.375rem;
    margin-right: 0;
  }
  
  .user-avatar, .bot-avatar {
    width: 2rem;
    height: 2rem;
    font-size: 0.75rem;
  }
  
  .message-content {
    padding: 0.5rem 0.75rem;
  }
  
  .message-text {
    font-size: 0.875rem;
    line-height: 1.4;
  }
  
  .message-text :deep(h1) {
    font-size: 1.125rem;
  }
  
  .message-text :deep(h2) {
    font-size: 1rem;
  }
  
  .message-text :deep(h3) {
    font-size: 0.875rem;
  }
  
  .message-text :deep(pre) {
    padding: 0.75rem;
    font-size: 0.75rem;
  }
  
  .message-text :deep(table) {
    font-size: 0.75rem;
  }
  
  .message-text :deep(th), .message-text :deep(td) {
    padding: 0.375rem;
  }
}

@media (max-width: 480px) {
  .message {
    max-width: 100%;
    margin-bottom: 0.5rem;
  }
  
  .message-avatar {
    margin-right: 0.25rem;
  }
  
  .user-message .message-avatar {
    margin-left: 0.25rem;
    margin-right: 0;
  }
  
  .user-avatar, .bot-avatar {
    width: 1.75rem;
    height: 1.75rem;
    font-size: 0.625rem;
  }
  
  .message-content {
    padding: 0.375rem 0.5rem;
  }
  
  .message-text {
    font-size: 0.8125rem;
    line-height: 1.3;
  }
  
  .message-text :deep(h1) {
    font-size: 1rem;
  }
  
  .message-text :deep(h2) {
    font-size: 0.875rem;
  }
  
  .message-text :deep(h3) {
    font-size: 0.8125rem;
  }
  
  .message-text :deep(pre) {
    padding: 0.5rem;
    font-size: 0.6875rem;
  }
  
  .message-text :deep(ul), .message-text :deep(ol) {
    padding-left: 1rem;
  }
  
  .error-level, .service-name, .error-code {
    font-size: 0.625rem;
    padding: 0.0625rem 0.25rem;
  }
}
</style>
