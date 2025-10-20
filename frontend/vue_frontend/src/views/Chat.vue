<template>
  <div class="chat-container">
    <div class="sidebar">
      <SessionList
        :sessions="sessions"
        :current-session="currentSession"
        :theme-label="themeLabel"
        @select="handleSelectSession"
        @delete="handleDeleteSession"
        @create="handleCreateSession"
        @toggleTheme="toggleTheme"
      />
      
      <div class="user-info">
        <div class="user-actions">
          <button class="secondary" @click="handleClearHistory">
            清空当前会话
          </button>
          <button class="danger" @click="handleLogout">
            退出登录
          </button>
        </div>
      </div>
    </div>
    
    <div class="chat-area">
      <div class="chat-header">
        <h1>DeepSeek-KAI.v.0.0.1 聊天</h1>
        <h2>当前会话: {{ currentSession }}</h2>
      </div>
      
      <div v-if="error" class="error-message">{{ error }}</div>
      
      <div class="messages-container">
        <div v-if="messages.length === 0" class="empty-state">
          开始与 DeepSeek-KAI.v.0.0.1 的对话吧！
        </div>
        
        <ChatMessage
          v-for="msg in messages"
          :key="msg.id"
          :is-user="msg.isUser"
          :content="msg.content"
          :timestamp="msg.timestamp"
        />
        
        <div v-if="loading" class="loading-indicator">
          <div class="loading"></div>
          <p>DeepSeek-KAI.v.0.0.1 正在思考...</p>
        </div>
      </div>
      
      <ChatInput
        :loading="loading"
        @send="handleSendMessage"
      />
    </div>
  </div>
</template>

<script setup>
import { onMounted, computed, ref } from 'vue';
import { useRouter } from 'vue-router';
import { useStore } from '../store';
import api from '../api';
import SessionList from '../components/SessionList.vue';
import ChatMessage from '../components/ChatMessage.vue';
import ChatInput from '../components/ChatInput.vue';

const store = useStore();
const router = useRouter();

// 计算属性
const sessions = computed(() => store.sessions);
const currentSession = computed(() => store.currentSession);
const messages = computed(() => store.messages[currentSession.value] || []);
const loading = computed(() => store.loading);
const error = computed(() => store.error);

// 初始化加载历史记录
const loadHistory = async (sessionId) => {
  try {
    store.setLoading(true);
    const response = await api.getHistory(sessionId);
    store.loadHistory(sessionId, response.data.history);
  } catch (err) {
    store.setError(err.response?.data?.error || '加载历史记录失败');
  } finally {
    store.setLoading(false);
  }
};

// 主题切换（明/暗）
const themeLabel = ref('深色主题');
const applyTheme = (theme) => {
  document.documentElement.setAttribute('data-theme', theme);
  localStorage.setItem('theme', theme);
  themeLabel.value = theme === 'dark' ? '浅色主题' : '深色主题';
};
const toggleTheme = () => {
  const current = document.documentElement.getAttribute('data-theme') || 'light';
  applyTheme(current === 'dark' ? 'light' : 'dark');
};

// 挂载时初始化主题并加载历史
onMounted(() => {
  const saved = localStorage.getItem('theme');
  const prefersDark = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
  applyTheme(saved || (prefersDark ? 'dark' : 'light'));
  loadHistory(currentSession.value);
});

// 处理选择会话
const handleSelectSession = async (sessionId) => {
  store.setCurrentSession(sessionId);
  await loadHistory(sessionId);
};

// 处理删除会话
const handleDeleteSession = async (sessionId) => {
  try {
    await api.clearHistory(sessionId);
    store.removeSession(sessionId);
    store.clearSessionMessages(sessionId);
  } catch (err) {
    store.setError(err.response?.data?.error || '删除会话失败');
  }
};

// 处理创建会话
const handleCreateSession = (sessionId) => {
  store.addSession(sessionId);
  store.clearSessionMessages(sessionId);
};

// 处理发送消息
const handleSendMessage = async (content) => {
  // 添加用户消息到界面
  store.addMessage(currentSession.value, true, content);
  
  try {
    store.setLoading(true);
    // 调用API发送消息
    const response = await api.chat(currentSession.value, content);
    // 添加机器人回复到界面
    store.addMessage(currentSession.value, false, response.data.reply);
  } catch (err) {
    store.setError(err.response?.data?.error || '发送消息失败');
  } finally {
    store.setLoading(false);
  }
};

// 处理清空历史
const handleClearHistory = async () => {
  if (confirm(`确定要清空当前会话 "${currentSession.value}" 的历史记录吗？`)) {
    try {
      await api.clearHistory(currentSession.value);
      store.clearSessionMessages(currentSession.value);
    } catch (err) {
      store.setError(err.response?.data?.error || '清空历史记录失败');
    }
  }
};

// 处理退出登录
const handleLogout = () => {
  if (confirm('确定要退出登录吗？')) {
    store.clearApiKey();
    router.push('/login');
  }
};
</script>

<style scoped>
/* 页面：聊天主界面
   目标：
   - 左侧会话/操作区 + 右侧聊天区的两栏布局
   - 在中小屏设备上切换为上下布局，保证可用性
   - 优化滚动条与消息容器的溢出处理 */
.chat-container {
  display: flex;
  height: 100vh;
}

/* 侧边栏：会话列表 + 操作区域 */
.sidebar {
  width: 300px;
  min-width: 250px;
  display: flex;
  flex-direction: column;
  background-color: var(--card-bg);
  border-right: 1px solid var(--border-color);
  transition: transform 0.3s ease;
}

.user-info {
  padding: 1rem;
  border-top: 1px solid var(--border-color);
}

/* 操作按钮区域：在小屏时纵向改横向排列 */
.user-actions {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.user-actions button {
  width: 100%;
  padding: 0.5rem;
  font-size: 0.875rem;
}

/* 聊天区域：主内容区，包含标题栏与消息列表 */
.chat-area {
  flex: 1;
  display: flex;
  flex-direction: column;
  background-color: var(--bg-color);
  min-width: 0; /* 防止flex子元素溢出 */
}

/* 标题栏：固定高度，防止被消息区挤压 */
.chat-header {
  padding: 1rem;
  background-color: var(--card-bg);
  border-bottom: 1px solid var(--border-color);
  flex-shrink: 0;
}

.chat-header h1 {
  color: var(--primary-color);
  margin-bottom: 0.25rem;
  font-size: 1.5rem;
}

.chat-header h2 {
  font-size: 1rem;
  color: var(--text-secondary);
  font-weight: 500;
}

/* 消息列表：滚动容器，启用平滑滚动 */
.messages-container {
  flex: 1;
  padding: 1rem;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  scroll-behavior: smooth;
}

.empty-state {
  margin: auto;
  color: var(--text-secondary);
  font-size: 1.25rem;
  text-align: center;
  padding: 2rem;
}

.loading-indicator {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin: 1rem auto;
  color: var(--text-secondary);
}

/* 响应式设计：在中小屏将布局改为上下结构，并调整间距与尺寸 */
@media (max-width: 768px) {
  .chat-container {
    flex-direction: column;
  }
  
  .sidebar {
    width: 100%;
    height: auto;
    max-height: 200px;
    order: 2;
  }
  
  .chat-area {
    order: 1;
    height: calc(100vh - 200px);
  }
  
  .user-actions {
    flex-direction: row;
  }
  
  .user-actions button {
    flex: 1;
  }
  
  .chat-header h1 {
    font-size: 1.25rem;
  }
  
  .messages-container {
    padding: 0.5rem;
  }
}

@media (max-width: 480px) {
  .sidebar {
    max-height: 150px;
  }
  
  .chat-area {
    height: calc(100vh - 150px);
  }
  
  .chat-header {
    padding: 0.75rem;
  }
  
  .chat-header h1 {
    font-size: 1.125rem;
  }
  
  .chat-header h2 {
    font-size: 0.875rem;
  }
  
  .user-info {
    padding: 0.75rem;
  }
  
  .user-actions button {
    padding: 0.375rem;
    font-size: 0.75rem;
  }
}

/* 滚动条样式：细滚动条，提高视觉品质 */
.messages-container::-webkit-scrollbar {
  width: 6px;
}

.messages-container::-webkit-scrollbar-track {
  background: var(--bg-color);
}

.messages-container::-webkit-scrollbar-thumb {
  background: var(--border-color);
  border-radius: 3px;
}

.messages-container::-webkit-scrollbar-thumb:hover {
  background: var(--text-secondary);
}

/* 消息容器优化 */
.messages-container {
  scroll-padding-bottom: 1rem;
}

/* 确保消息不会超出容器 */
.message {
  word-wrap: break-word;
  overflow-wrap: break-word;
}
</style>
