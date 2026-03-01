const http = require('http');
const https = require('https');
const { URL } = require('url');

const TARGET = process.argv[2] || process.env.QA_TARGET || 'https://example.com';
if (TARGET === 'https://example.com') {
  console.log('Usage: node proxy.js <TARGET_URL>');
  console.log('  e.g. node proxy.js https://my-site.com');
  process.exit(1);
}

const server = http.createServer((req, res) => {
  const targetUrl = new URL(req.url, TARGET);

  const options = {
    hostname: targetUrl.hostname,
    port: 443,
    path: targetUrl.pathname + targetUrl.search,
    method: req.method,
    headers: {
      ...req.headers,
      host: targetUrl.hostname,
      referer: TARGET + '/',
      origin: TARGET,
      'accept-encoding': 'identity', // no compression
    },
  };

  const proxyReq = https.request(options, (proxyRes) => {
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
        body = body.replace(new RegExp(TARGET.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'g'), '');
        // Fix Content-Length after modification
        delete headers['content-length'];
        headers['content-length'] = Buffer.byteLength(body);
        res.writeHead(proxyRes.statusCode, headers);
        res.end(body);
      });
    } else {
      res.writeHead(proxyRes.statusCode, headers);
      proxyRes.pipe(res);
    }
  });

  proxyReq.on('error', (err) => {
    console.error('Proxy error:', err.message);
    res.writeHead(502);
    res.end('Proxy error: ' + err.message);
  });

  req.pipe(proxyReq);
});

server.listen(8765, () => {
  console.log('Reverse proxy running on http://localhost:8765');
  console.log('Proxying to:', TARGET);
});
