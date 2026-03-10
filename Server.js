const express = require('express');
const { createBareServer } = require('@tomphttp/bare-server-node');
const path = require('path');
const http = require('http');
const fs = require('fs');

const app = express();
const server = http.createServer(app);
const bare = createBareServer('/bare/');

const PORT = 8080;

// Serve static files (our UI + Ultraviolet)
app.use(express.static(__dirname));
app.use('/uv/', express.static(path.join(__dirname, 'uv')));

// Ultraviolet handler
app.use('/uv/service/', (req, res, next) => {
  req.url = '/uv/' + req.url.replace(/^\/uv\/service\//, '');
  express.static(path.join(__dirname, 'uv'))(req, res, next);
});

// Bare server for codec & transport
app.use('/bare/', (req, res) => {
  if (bare.shouldRoute(req)) {
    bare.routeRequest(req, res);
  } else {
    res.status(400).send('Bad Request');
  }
});

// WebSocket for Bare
server.on('upgrade', (req, socket, head) => {
  if (req.url.startsWith('/bare/')) {
    bare.routeUpgrade(req, socket, head);
  } else {
    socket.end();
  }
});

// Main proxy page
app.get('/', (req, res) => {
  res.sendFile(path.join(__dirname, 'index.html'));
});

server.listen(PORT, () => {
  console.log(`
  ╔═══════════════════════════════════╗
  ║       Elijah’s Proxy V7           ║
  ║       Running on port ${PORT}            ║
  ║       http://127.0.0.1:${PORT}       ║
  ╚═══════════════════════════════════╝
  `);
});