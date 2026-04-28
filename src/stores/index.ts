import * as TransformUtils  from '@/utils/transform'
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

// 发起 fetch 请求
async function callLLM(messages: string, controller?: AbortController):Promise<{error: number
  reader: ReadableStreamDefaultReader<string> | null}> {
  if(payload && messages){
    payload.messages[1]!.content = messages
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