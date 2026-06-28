/// <reference types="vite/client" />

declare module 'katex/contrib/auto-render/splitAtDelimiters' {
  interface DelimiterSpec {
    left: string;
    right: string;
    display: boolean;
  }
  interface SplitAtDelimiterData {
    type: 'text' | 'math';
    data: string;
    rawData?: string;
    display?: boolean;
  }
  function splitAtDelimiters(text: string, delimiters: DelimiterSpec[]): SplitAtDelimiterData[];
  export default splitAtDelimiters;
}
