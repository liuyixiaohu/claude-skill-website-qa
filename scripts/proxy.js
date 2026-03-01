const http = require('http');
const https = require('https');
const { URL } = require('url');

const TARGET = process.argv[2] || process.env.QA_TARGET || 'https://example.com';
if (TARGET === 'https://example.com') {
  console.log('Usage: node proxy.js <TARGET_URL> [PORT]');
  console.log('  e.g. node proxy.js https://my-site.com');
  console.log('  e.g. node proxy.js https://my-site.com 9000');
  process.exit(1);
}

const PARSED_TARGET = new URL(TARGET);
const IS_HTTPS = PARSED_TARGET.protocol === 'https:';
const TARGET_PORT = parseInt(PARSED_TARGET.port) || (IS_HTTPS ? 443 : 80);
const LISTEN_PORT = parseInt(process.argv[3] || process.env.QA_PROXY_PORT || '8765', 10);
const requestFn = IS_HTTPS ? https.request : http.request;

// Pre-compile regex once at startup (avoids recompilation per HTML request)
const TARGET_REGEX = new RegExp(TARGET.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'g');

const server = http.createServer((req, res) => {
  const targetUrl = new URL(req.url, TARGET);

  const options = {
    hostname: targetUrl.hostname,
    port: TARGET_PORT,
    path: targetUrl.pathname + targetUrl.search,
    method: req.method,
    headers: {
      ...req.headers,
      host: targetUrl.hostname,
      referer: TARGET + '/',
      origin: TARGET,
      'accept-encoding': 'identity', // no compression — simplifies HTML rewriting
    },
  };

  const proxyReq = requestFn(options, (proxyRes) => {
    const contentType = proxyRes.headers['content-type'] || '';
    const headers = { ...proxyRes.headers };

    // Remove security headers
    delete headers['content-security-policy'];
    delete headers['x-frame-options'];
    delete headers['strict-transport-security'];
    delete headers['content-encoding'];

    if (contentType.includes('text/html')) {
      let body = '';
      proxyRes.on('data', chunk => body += chunk);
      proxyRes.on('end', () => {
        body = body.replace(TARGET_REGEX, '');
        delete headers['content-length'];
        headers['content-length'] = Buffer.byteLength(body);
        res.writeHead(proxyRes.statusCode, headers);
        res.end(body);
      });
      proxyRes.on('error', (err) => {
        console.error('Upstream response error:', err.message);
        if (!res.headersSent) res.writeHead(502);
        res.end('Upstream error');
      });
    } else {
      res.writeHead(proxyRes.statusCode, headers);
      proxyRes.pipe(res);
    }
  });

  proxyReq.on('error', (err) => {
    console.error('Proxy error:', err.message);
    if (!res.headersSent) res.writeHead(502);
    res.end('Proxy error: ' + err.message);
  });

  req.on('error', (err) => {
    console.error('Client request error:', err.message);
    proxyReq.destroy();
  });

  req.pipe(proxyReq);
});

// Graceful shutdown
process.on('SIGTERM', () => { server.close(() => process.exit(0)); });
process.on('SIGINT', () => { server.close(() => process.exit(0)); });

server.listen(LISTEN_PORT, () => {
  console.log(`Reverse proxy running on http://localhost:${LISTEN_PORT}`);
  console.log('Proxying to:', TARGET, `(${IS_HTTPS ? 'HTTPS' : 'HTTP'}, port ${TARGET_PORT})`);
});
