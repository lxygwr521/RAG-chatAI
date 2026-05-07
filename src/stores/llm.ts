import * as TransformUtils  from '@/utils/transform'
import type { UploadFile } from '@/components/chat/types'

interface Payload {
  model: string;
  stream: boolean;
  messages: Array<{ role: string; content: string }>;
}

// llm api 地址
const url = 'https://api.deepseek.com/chat/completions';

// 请求头配置
const headers = {
  'Content-Type': 'application/json',
  'Authorization': `Bearer ${import.meta.env.VITE_DEEPSEEK_API_KEY}`
};

// 请求体数据
const payload: Payload = {
  model: 'deepseek-chat',
  stream: true,
  messages: [
    { role: "system", content: "You are a helpful assistant." },
    { role: "user", content: "你好 DeepSeek" }
  ]
};

async function readFiles(files: UploadFile[]): Promise<string> {
  const results = await Promise.all(
    files.map(
      (item) =>
        new Promise<string>((resolve, reject) => {
          const reader = new FileReader()
          reader.onload = () => resolve(reader.result as string)
          reader.onerror = () => reject(new Error(`读取文件失败: ${item.file.name}`))
          reader.readAsText(item.file)
        })
    )
  )
  return results
    .map((content, i) => {
      const { name } = files[i].file
      return `[文件: ${name}]\n${content}`
    })
    .join('\n\n')
}

async function buildPrompt(question: string, files: UploadFile[]): Promise<string> {
  if (!files || files.length === 0) return question
  const fileContent = await readFiles(files)
  return `${fileContent}\n\n---\n\n${question}`.trim()
}


// 发起 fetch 请求
async function callLLM(question: string, files: UploadFile[], controller?: AbortController): Promise<{error: number
  reader: ReadableStreamDefaultReader<string> | null}> {
  const prompt = await buildPrompt(question, files)
  if(payload){
    payload.messages[1]!.content = prompt
  }
  try {
    const response = await fetch(url, {
      method: 'POST',
      headers,
      body: JSON.stringify(payload),
      signal: controller?.signal,
    });
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    if(response.body){
      const reader = response.body
      .pipeThrough(new TextDecoderStream())
      .pipeThrough(TransformUtils.splitStream('\n'))
      .getReader()
      return {error:0,reader:reader as ReadableStreamDefaultReader<string>}
    }else{
      return {error:1,reader:null}
    }
  } catch (error) {
    return {error:1,reader:null}
  }
}
// while (true) {
//   const { done, value } = await reader.read();

//   if (done) break;

//   console.log(value); // 一行数据
// }

export default callLLM