<script setup lang="ts">
import Chat from './pages/chat.vue'
defineOptions({
  name: 'App'
})
import { useCopyCode } from '@/hooks/useCopyCode'
useCopyCode()
</script>

<template>
  <Chat />
</template>

<style scoped>
</style>
