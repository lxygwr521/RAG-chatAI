export { default as UserMsg } from './UserMsg.vue'
export { default as AssistantMsg } from './AssistantMsg.vue'
export { default as ChatInput } from './ChatInput.vue'
export { default as QuickQuestions } from './QuickQuestions.vue'

export const mockQuestions = [
  '如何学习 Vue 3？',
  'Tailwind CSS 和 SCSS 有什么区别？',
  '什么是 Composition API？',
]

export const mockResponses = [
  'Vue 3 是一个渐进式 JavaScript 框架，它引入了 Composition API 来提供更灵活的代码组织方式...',
  'Tailwind CSS 是一个utility-first的CSS框架，而SCSS是CSS的预处理语言，它们可以结合使用...',
  'Composition API 是 Vue 3 引入的新特性，它允许你使用导入的函数来组织逻辑，而不是依赖选项式 API...',
]
