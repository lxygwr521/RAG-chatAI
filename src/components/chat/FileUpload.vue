<script setup lang="ts">
import { ref, computed } from 'vue'
import { UploadFile } from './types'
const TEXT_EXTENSIONS = [
  'txt', 'md', 'markdown', 'log', 'json', 'csv',
  'xml', 'yml', 'yaml', 'ini', 'conf',
]

const MAX_SIZE = 10 * 1024 * 1024 // 10MB


const files = ref<UploadFile[]>([])
const fileInputRef = ref<HTMLInputElement | null>(null)

const hasFiles = computed(() => files.value.length > 0)

function isAllowedType(file: File): boolean {
  if (file.type.startsWith('text/')) return true
  const ext = file.name.split('.').pop()?.toLowerCase()
  return !!ext && TEXT_EXTENSIONS.includes(ext)
}

function getFileType(file: File): string {
  return file.name.split('.').pop()?.toUpperCase() ?? 'TXT'
}

function getFileIcon(): string {
  return 'txt'
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

function removeFile(id: string) {
  files.value = files.value.filter((f) => f.id !== id)
}

function clearFiles() {
  files.value = []
}

async function readFiles(): Promise<string> {
  //读取每个文件 返回结果数组
  const results = await Promise.all(
    files.value.map(
      (item) =>
        new Promise<string>((resolve, reject) => {
          const reader = new FileReader()
          reader.onload = () => resolve(reader.result as string)
          reader.onerror = () => reject(new Error(`读取文件失败: ${item.file.name}`))

          reader.readAsText(item.file)
        })
    )
  )
  // debugger
  return results
    .map((content, i) => {
      const { name } = files.value[i].file
      return `[文件: ${name}]\n${content}`
    })
    .join('\n\n')
}

function validateFile(file: File): string | null {
  if (!isAllowedType(file)) return `不支持 ${file.name.split('.').pop()} 文件类型`
  if (file.size > MAX_SIZE) return '文件大小超出限制（最大 10MB）'
  return null
}

function addFiles(newFiles: FileList | File[]) {
  for (const file of Array.from(newFiles)) {
    const error = validateFile(file)
    if (error) {
      window.$message?.error(error)
      continue
    }
    files.value.push({
      id: `${Date.now()}-${Math.random().toString(36).slice(2)}`,
      file,
    })
  }
}

function handleFileChange(event: Event) {
  const target = event.target as HTMLInputElement
  if (target.files?.length) addFiles(target.files)
  target.value = ''
}

function handleClick() {
  fileInputRef.value?.click()
}

defineExpose({
  files,
  readFiles,
  removeFile,
  clearFiles,
})
</script>

<template>
  <!-- Hidden file input -->
  <input
    ref="fileInputRef"
    type="file"
    class="file-upload__input"
    multiple
    @change="handleFileChange"
  />

  <!-- Upload trigger button -->
  <button
    type="button"
    class="file-upload__trigger"
    @click="handleClick"
    title="上传文件"
  >
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
      <path d="M21 15V19C21 20.1 20.1 21 19 21H5C3.9 21 3 20.1 3 19V15M17 8L12 3M12 3L7 8M12 3V15" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
    </svg>
  </button>
</template>

<style scoped lang="scss">
.file-upload__input {
  display: none;
}

.file-upload__trigger {
  width: 2.25rem;
  height: 2.25rem;
  border: none;
  background: transparent;
  color: $color-gray-500;
  border-radius: $radius-lg;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: color $transition-fast, background-color $transition-fast;

  &:hover {
    color: $color-primary-500;
    background: rgba($color-primary-500, 0.08);
  }
}
</style>
