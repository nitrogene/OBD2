import http from 'node:http';
import { spawn } from 'node:child_process';
import path from 'node:path';
import fs from 'node:fs';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const PORT_START = 49620;
const PORT_END = 49629;
const SERVICE_ID = 'easyeda-bridge';

function checkHealth(port) {
  return new Promise((resolve) => {
    const req = http.get(`http://127.0.0.1:${port}/health`, { timeout: 300 }, (res) => {
      let data = '';
      res.on('data', (chunk) => (data += chunk));
      res.on('end', () => {
        try {
          const json = JSON.parse(data);
          resolve(json && json.service === SERVICE_ID);
        } catch {
          resolve(false);
        }
      });
    });
    req.on('timeout', () => {
      req.destroy();
      resolve(false);
    });
    req.on('error', () => {
      resolve(false);
    });
  });
}

async function isBridgeRunning() {
  for (let port = PORT_START; port <= PORT_END; port++) {
    if (await checkHealth(port)) {
      return true;
    }
  }
  return false;
}

async function main() {
  // Drain stdin to avoid blocking hook runner
  process.stdin.resume();

  try {
    const running = await isBridgeRunning();
    fs.appendFileSync(path.resolve(__dirname, 'hook-audit.log'), `[${new Date().toISOString()}] PreInvocation hook triggered - bridge running: ${running}\n`);
    if (!running) {
      const bridgeScript = path.resolve(__dirname, 'skills', 'easyeda-api', 'scripts', 'bridge-server.mjs');
      const bridgeCwd = path.resolve(__dirname, 'skills', 'easyeda-api');
      const logFile = path.resolve(__dirname, 'easyeda-bridge.log');

      const out = fs.openSync(logFile, 'a');
      const child = spawn(process.execPath, [bridgeScript], {
        cwd: bridgeCwd,
        detached: true,
        stdio: ['ignore', out, out],
        windowsHide: true,
      });
      child.unref();

      // Give it a brief moment to initialize
      await new Promise((r) => setTimeout(r, 400));
    }
  } catch (err) {
    // Fail gracefully so hooks never break conversation loop
  }

  process.stdout.write(JSON.stringify({}));
  process.exit(0);
}

main();
