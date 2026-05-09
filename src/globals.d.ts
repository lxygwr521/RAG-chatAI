// Global type augmentations for naive-ui message plugin on window
import type { Message } from 'naive-ui'

declare global {
  interface Window {
    $message: Message
  }
}
