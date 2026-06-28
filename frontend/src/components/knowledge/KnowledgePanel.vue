<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { fetchDocuments, uploadDocuments, deleteDocument, formatFileSize, type DocumentInfo } from '@/api/knowledge'

const emit = defineEmits<{
  close: []
}>()
// KnowledgePanel 决定知识库里有什么
const documents = ref<DocumentInfo[]>([])
const loading = ref(false)
const uploading = ref(false)
const error = ref('')

const ALLOWED_EXTENSIONS = '.txt,.md,.markdown,.pdf,.csv,.json,.log,.xml,.yml,.yaml,.ini,.conf'

async function loadDocuments() {
  loading.value = true
  try {
    documents.value = await fetchDocuments()
  } catch (e) {
    error.value = `加载失败: ${e}`
  } finally {
    loading.value = false
  }
}

async function handleUpload(event: Event) {
  const input = event.target as HTMLInputElement
  const files = input.files
  if (!files || files.length === 0) return

  uploading.value = true
  error.value = ''
  try {
    await uploadDocuments(Array.from(files))
    await loadDocuments()
  } catch (e) {
    error.value = `上传失败: ${e}`
  } finally {
    uploading.value = false
    input.value = ''
  }
}

async function handleDelete(id: string) {
  try {
    await deleteDocument(id)
    documents.value = documents.value.filter(d => d.id !== id)
  } catch (e) {
    error.value = `删除失败: ${e}`
  }
}

onMounted(loadDocuments)
</script>

<template>
  <div class="knowledge-panel">
    <div class="knowledge-header">
      <h3 class="knowledge-title">📚 知识库</h3>
      <button class="knowledge-close" @click="emit('close')">✕</button>
    </div>

    <div class="knowledge-upload">
      <label class="upload-btn" :class="{ disabled: uploading }">
        {{ uploading ? '⏳ 处理中...' : '📎 上传文档' }}
        <input
          type="file"
          :accept="ALLOWED_EXTENSIONS"
          multiple
          :disabled="uploading"
          @change="handleUpload"
          hidden
        />
      </label>
      <span class="upload-hint">支持 txt, md, pdf, csv, json, log, xml, yml, ini, conf 等</span>
    </div>

    <div v-if="error" class="knowledge-error">{{ error }}</div>

    <div class="knowledge-list">
      <div v-if="loading" class="knowledge-empty">加载中...</div>
      <div v-else-if="documents.length === 0" class="knowledge-empty">
        暂无文档，上传第一个文档开始构建知识库
      </div>
      <div
        v-for="doc in documents"
        :key="doc.id"
        class="knowledge-item"
      >
        <div class="doc-info">
          <span class="doc-name" :title="doc.filename">{{ doc.filename }}</span>
          <span class="doc-meta">
            {{ doc.file_type.toUpperCase() }} · {{ formatFileSize(doc.file_size) }} · {{ doc.chunk_count }} 块
          </span>
        </div>
        <span class="doc-status" :class="doc.status">
          {{ doc.status === 'ready' ? '✓' : doc.status === 'processing' ? '⏳' : '✗' }}
        </span>
        <button class="doc-delete" @click="handleDelete(doc.id)" title="删除">🗑</button>
      </div>
    </div>
  </div>
</template>

<style scoped lang="scss">
.knowledge-panel {
  width: 320px;
  height: 100vh;
  display: flex;
  flex-direction: column;
  background: $color-bg-primary;
  border-left: 1px solid $color-border-light;
  font-size: $font-size-sm;
}

.knowledge-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: $spacing-4;
  border-bottom: 1px solid $color-border-light;
}

.knowledge-title {
  font-size: $font-size-base;
  font-weight: $font-weight-semibold;
  margin: 0;
}

.knowledge-close {
  border: none;
  background: none;
  cursor: pointer;
  font-size: $font-size-lg;
  color: $color-gray-400;
  &:hover { color: $color-gray-600; }
}

.knowledge-upload {
  padding: $spacing-4;
  border-bottom: 1px solid $color-border-light;
  display: flex;
  flex-direction: column;
  gap: $spacing-2;
}

.upload-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: $spacing-2 $spacing-4;
  background: $color-primary-500;
  color: white;
  border-radius: $radius-lg;
  cursor: pointer;
  font-size: $font-size-sm;
  font-weight: $font-weight-medium;

  &:hover:not(.disabled) { background: $color-primary-600; }
  &.disabled { opacity: 0.5; cursor: not-allowed; }
}

.upload-hint {
  font-size: $font-size-xs;
  color: $color-text-muted;
}

.knowledge-error {
  padding: $spacing-2 $spacing-4;
  color: $color-error;
  font-size: $font-size-xs;
  background: #fef2f2;
}

.knowledge-list {
  flex: 1;
  overflow-y: auto;
  padding: $spacing-2;
}

.knowledge-empty {
  padding: $spacing-8 $spacing-4;
  text-align: center;
  color: $color-text-muted;
  font-size: $font-size-sm;
}

.knowledge-item {
  display: flex;
  align-items: center;
  gap: $spacing-2;
  padding: $spacing-3;
  border-radius: $radius-lg;
  margin-bottom: $spacing-1;

  &:hover { background: $color-gray-50; }
}

.doc-info {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.doc-name {
  font-weight: $font-weight-medium;
  color: $color-text-primary;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.doc-meta {
  font-size: $font-size-xs;
  color: $color-text-muted;
}

.doc-status {
  font-size: $font-size-sm;
  &.ready { color: $color-success; }
  &.processing { color: $color-warning; }
  &.error { color: $color-error; }
}

.doc-delete {
  border: none;
  background: none;
  cursor: pointer;
  font-size: $font-size-sm;
  opacity: 0.5;
  &:hover { opacity: 1; }
}
</style>
