<script setup lang="ts">
import { ref } from 'vue'
import ConversationSidebar from '@/components/layout/ConversationSidebar.vue'
import Chat from './pages/chat.vue'
import KnowledgePanel from '@/components/knowledge/KnowledgePanel.vue'
import { useCopyCode } from '@/hooks/useCopyCode'

defineOptions({
  name: 'App'
})

useCopyCode()

const showKnowledge = ref(false)
</script>

<template>
  <div class="app-layout flex h-screen overflow-hidden">
    <ConversationSidebar />
    <Chat class="flex-1 min-w-0" />

    <!-- Knowledge panel toggle -->
    <button
      class="knowledge-toggle"
      :class="{ active: showKnowledge }"
      @click="showKnowledge = !showKnowledge"
      title="知识库"
    >
      📚
    </button>

    <!-- Knowledge panel (slide-in) -->
    <Transition name="slide">
      <KnowledgePanel
        v-if="showKnowledge"
        @close="showKnowledge = false"
      />
    </Transition>
  </div>
</template>

<style scoped>
.knowledge-toggle {
  position: fixed;
  right: 16px;
  bottom: 100px;
  width: 44px;
  height: 44px;
  border-radius: 50%;
  border: 1px solid #e5e7eb;
  background: white;
  font-size: 1.25rem;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 2px 8px rgba(0,0,0,0.1);
  z-index: 50;
  transition: all 0.2s;
}

.knowledge-toggle:hover,
.knowledge-toggle.active {
  background: #8b5cf6;
  border-color: #8b5cf6;
}

/* Slide transition for knowledge panel */
.slide-enter-active,
.slide-leave-active {
  transition: transform 0.25s ease;
}

.slide-enter-from,
.slide-leave-to {
  transform: translateX(100%);
}
</style>
