const allowedMediaTypes = [
  'image/*',
  'video/*',
  'audio/*',
  'application/pdf',
  'application/msword',
  'application/vnd.openxmlformats-officedocument.*',
  'text/plain',
  'text/csv',
];

const deniedTypes = [
  'image/svg+xml',
  'application/vnd.microsoft.portable-executable',
  'application/x-msdownload',
  'application/x-msdos-program',
  'application/x-executable',
  'application/x-dosexec',
  'application/x-sh',
  'text/x-shellscript',
  'application/x-mach-binary',
];

module.exports = ({ env }) => ({
  'users-permissions': {
    config: {
      jwtManagement: 'refresh',
      sessions: {
        httpOnly: true,
      },
    },
  },
  upload: {
    config: {
      // Cloudflare R2 in production (hosts have no permanent disk); local public/uploads when it isn't configured
      ...(env('R2_BUCKET') && {
        provider: 'aws-s3',
        providerOptions: {
          // Public address of the bucket, e.g. https://media.devliqly.in
          baseUrl: env('R2_PUBLIC_URL'),
          rootPath: 'blog',
          s3Options: {
            endpoint: `https://${env('R2_ACCOUNT_ID')}.r2.cloudflarestorage.com`,
            region: 'auto',
            credentials: {
              accessKeyId: env('R2_ACCESS_KEY_ID'),
              secretAccessKey: env('R2_SECRET_ACCESS_KEY'),
            },
            // R2 has no per-object ACLs; access is set on the bucket
            params: { Bucket: env('R2_BUCKET'), ACL: undefined },
          },
        },
      }),
      security: {
        allowedTypes: allowedMediaTypes,
        deniedTypes,
      },
    },
  },
});
