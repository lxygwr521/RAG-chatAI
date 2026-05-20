# Mock 流式响应内容

# **💡说明**

> - 请注意，本次展示回复内容为**模拟 Event Stream 静态输出**，非真实接口调用。
>
>- 如果需要调用真实的 GPT 接口，请拉取本仓库，在本地开发环境中配置相应的 `API` 密钥和`接口地址`。

## <a target="_blank" href="https://github.com/lxygwr521/chatAI">关于本仓库</a>

![GitHub Pages](https://img.shields.io/badge/gh--pages-passing-brightgreen)
![Build Status](https://img.shields.io/badge/build-passing-brightgreen)
![Thanks](https://img.shields.io/badge/thanks-%E2%9D%A4-pink)
![License](https://img.shields.io/badge/license-MIT-blue)

---

## Mock 1：代码展示

以下是一个简单的快速排序实现：

```typescript
function quickSort(arr: number[]): number[] {
  if (arr.length <= 1) return arr;

  const pivot = arr[Math.floor(arr.length / 2)];
  const left = arr.filter(x => x < pivot);
  const mid = arr.filter(x => x === pivot);
  const right = arr.filter(x => x > pivot);

  return [...quickSort(left), ...mid, ...quickSort(right)];
}

console.log(quickSort([3, 6, 8, 10, 1, 2, 1]));
// 输出: [1, 1, 2, 3, 6, 8, 10]
```

这段代码的核心思想是：
- **选取基准值**（pivot）
- **分区**：小于 pivot 的放左边，大于的放右边
- **递归**对左右两部分继续排序

---



## Mock2：一般对话

你好！我是 chatAI，一个基于 Vue 3 的 AI 对话助手。

我可以帮你：

- **解答问题** — 从编程到日常生活的各类疑问
- **代码编写** — 支持多种语言的代码生成与解释
- **文档撰写** — 帮你起草文章、邮件、报告等
- **数据分析** — 解释数据模式，提供洞见

你可以点击下方的快捷问题快速开始，也可以直接输入任何问题。试试看吧！

## Mock3：数学公式

* 纳维-斯托克斯方程

$$
\rho\left(\frac{\partial \vec{u}}{\partial t} + \vec{u} \cdot \nabla\vec{u}\right) = -\nabla p + \nabla \cdot \left[\mu\left(\nabla\vec{u} + (\nabla\vec{u})^T\right)\right] + \vec{f}
$$

* 薛定谔波动方程

$$
i\hbar\frac{\partial \psi(\vec{r},t)}{\partial t} = \left[-\frac{\hbar^2}{2m}\nabla^2 + V(\vec{r},t)\right]\psi(\vec{r},t)
$$

## Mock3：表格
| 技术栈 | 说明 | 官网 |
|--------|------|------|
| React | 用户界面库 | [链接](https://reactjs.org) |
| Vue.js | 渐进式框架 | [链接](https://vuejs.org) |
| Angular | 完整的框架 | [链接](https://angular.io) |