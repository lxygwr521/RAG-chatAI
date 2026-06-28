// SSE event object emitted by the stream reader
export interface SSEChunk {
  event: string | null   // e.g. "delta", "tool_call", "tool_result", "done", "error"
  data: string           // JSON string or "[DONE]"
}

// 处理SSE格式的数据（支持 event: + data: 类型化事件）
const processSSE = (buffer: string, controller: TransformStreamDefaultController, splitOn: string, _lastEventType: string | null) => {
    const parts = buffer.split(splitOn)
    parts.pop()
    const lastPart = parts.pop()

    let currentEventType: string | null = null

    for (const part of parts) {
      const trimmedPart = part.trim()
      if (!trimmedPart) continue

      // Capture event type: event: <name>
      if (trimmedPart.startsWith('event:')) {
        currentEventType = trimmedPart.replace(/^event:\s*/, '').trim()
        continue
      }

      if (trimmedPart.startsWith('data:')) {
        const content = trimmedPart.replace(/^data: /, '').trim()
        if (content) {
          // Emit as typed SSEChunk if we have an event type, else raw string
          if (currentEventType) {
            controller.enqueue(JSON.stringify({ event: currentEventType, data: content }))
          } else {
            // Backward-compat: just the JSON data string
            controller.enqueue(content)
          }
        }
        // Reset event type for next block
        currentEventType = null
      } else {
        controller.enqueue(trimmedPart)
      }
    }

    return lastPart ?? ''
  }

  // 处理可能包含多个JSON对象的数据
  const processJSON = (buffer: string, controller: TransformStreamDefaultController) => {
    let remaining = buffer
    let processed = false

    while (remaining.trim() !== '') {
      let validJSON = ''
      let validJSONEndIndex = -1

      for (let i = 0; i <= remaining.length; i++) {
        try {
          const possibleJSON = remaining.substring(0, i)
          if (possibleJSON.endsWith('}')) {
            JSON.parse(possibleJSON)
            validJSON = possibleJSON
            validJSONEndIndex = i
            break
          }
        } catch (e) {
          // 继续尝试
        }
      }

      if (validJSON) {
        try {
          JSON.parse(validJSON)
          controller.enqueue(validJSON)
          remaining = remaining.substring(validJSONEndIndex).trim()
          processed = true
        } catch (e) {
          break
        }
      } else {
        break
      }
    }

    return processed ? remaining : buffer
  }

  export const splitStream = (splitOn: string) => {
    let buffer = ''

    return new TransformStream({
      transform(chunk: Uint8Array | string, controller) {
        buffer += chunk
        const trimmedBuffer = buffer.trim()

        if (trimmedBuffer.startsWith('event:') || trimmedBuffer.startsWith('data:')) {
          // SSE格式 (支持类型化事件: event: delta + data: {...})
          buffer = processSSE(buffer, controller, splitOn, null)
        } else if (trimmedBuffer.startsWith('{') && (
            trimmedBuffer.includes('"model"') ||
            trimmedBuffer.includes('"message"') ||
            trimmedBuffer.includes('"done"'))) {
          const newBuffer = processJSON(buffer, controller)

          if (newBuffer === buffer) {
            controller.enqueue(chunk)
            buffer = ''
          } else {
            buffer = newBuffer
          }
        } else {
          controller.enqueue(chunk)
          buffer = ''
        }
      },

      flush(controller) {
        if (buffer.trim() !== '') {
          try {
            controller.enqueue(buffer.trim())
          } catch (e) {
            controller.enqueue(buffer)
          }
        }
      }
    })
  }
