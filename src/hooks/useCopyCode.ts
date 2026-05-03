export function useCopyCode() {
    debugger
    const timeoutIdMap: WeakMap<HTMLElement, NodeJS.Timeout> = new WeakMap()
    window.addEventListener('click', (e) => {
      const el = e.target as HTMLElement
      if (!el.matches('div[class*="language-"] button.markdown-code-copy')) return
      // 通过 DOM 关系找到按钮同级的 <pre> 代码区
      const parent = el.parentElement
      const sibling = parent?.nextElementSibling
      if (!parent || !sibling) {
        return
      }
      // 如果是 shell 类语言（bash/shell/zsh），去掉命令行的 $ 或 > 前缀
      const isShell = /language-(shellscript|shell|bash|sh|zsh)/.test(
        parent.className
      )
      // 忽略的节点，比如代码块的标题、语言标签等
      const ignoredNodes = []
  
      // Clone the node and remove the ignored nodes
      const clone = sibling.cloneNode(true) as HTMLElement
      if (ignoredNodes.length) {
        clone
          .querySelectorAll(ignoredNodes.join(','))
          .forEach((node) => node.remove())
      }
  
      let text = clone.textContent || ''
  
      if (isShell) {
        text = text.replace(/^ *(\$|>) /gm, '').trim()
      }
  
      copyToClipboard(text).then(() => {
        el.classList.add('copied')
        clearTimeout(timeoutIdMap.get(el))
        const timeoutId = setTimeout(() => {
          el.classList.remove('copied')
          el.blur()
          timeoutIdMap.delete(el)
        }, 2000)
        timeoutIdMap.set(el, timeoutId)
      })
    })
  }
  
  async function copyToClipboard(text: string) {
    try {
      return navigator.clipboard.writeText(text)
    } catch {
      const element = document.createElement('textarea')
      const previouslyFocusedElement = document.activeElement
  
      element.value = text
  
      // Prevent keyboard from showing on mobile
      element.setAttribute('readonly', '')
  
      element.style.contain = 'strict'
      element.style.position = 'absolute'
      element.style.left = '-9999px'
      element.style.fontSize = '12pt' // Prevent zooming on iOS
  
      const selection = document.getSelection()
      const originalRange = selection
        ? selection.rangeCount > 0 && selection.getRangeAt(0)
        : null
  
      document.body.appendChild(element)
      element.select()
  
      // Explicit selection workaround for iOS
      element.selectionStart = 0
      element.selectionEnd = text.length
  
      document.execCommand('copy')
      document.body.removeChild(element)
  
      if (originalRange) {
        selection!.removeAllRanges() // originalRange can't be truthy when selection is falsy
        selection!.addRange(originalRange)
      }
  
      // Get the focus back on the previously focused element, if any
      if (previouslyFocusedElement) {
        (previouslyFocusedElement as HTMLElement).focus()
      }
    }
  }
  