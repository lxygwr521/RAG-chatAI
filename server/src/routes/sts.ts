import { Router } from 'express'
import { STS } from 'ali-oss'
import type { Request, Response } from 'express'

const router = Router()

router.get('/', async (_req: Request, res: Response) => {
  debugger
  const { ALIYUN_ACCESS_KEY_ID, ALIYUN_ACCESS_KEY_SECRET, OSS_ROLE_ARN, OSS_REGION, OSS_BUCKET } = process.env
  console.log(ALIYUN_ACCESS_KEY_ID, ALIYUN_ACCESS_KEY_SECRET, OSS_ROLE_ARN, OSS_REGION, OSS_BUCKET);
  

  if (!ALIYUN_ACCESS_KEY_ID || !ALIYUN_ACCESS_KEY_SECRET) {
    res.status(500).json({ error: 'OSS credentials not configured' })
    return
  }

  try {
    const client = new STS({
      accessKeyId: ALIYUN_ACCESS_KEY_ID,
      accessKeySecret: ALIYUN_ACCESS_KEY_SECRET,
    })

    const result = await client.assumeRole(
      OSS_ROLE_ARN!,
      undefined,
      3600
    )

    const { credentials } = result

    res.json({
      AccessKeyId: credentials.AccessKeyId,
      AccessKeySecret: credentials.AccessKeySecret,
      SecurityToken: credentials.SecurityToken,
      Expiration: credentials.Expiration,
      Region: OSS_REGION || 'oss-cn-hangzhou',
      Bucket: OSS_BUCKET || '',
    })
  } catch (err) {
    console.error('[STS] Error:', err)
    res.status(500).json({ error: 'Failed to generate STS token' })
  }
})

export default router
