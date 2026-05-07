declare module 'ali-oss/lib/sts.js' {
  interface STSOptions {
    accessKeyId: string
    accessKeySecret: string
  }

  interface AssumeRoleResult {
    credentials: {
      AccessKeyId: string
      AccessKeySecret: string
      SecurityToken: string
      Expiration: string
    }
    resp: unknown
  }

  class STS {
    constructor(options: STSOptions)
    assumeRole(
      roleArn: string,
      policy?: string | object,
      durationSeconds?: number
    ): Promise<AssumeRoleResult>
  }

  export default STS
}
