#!/usr/bin/env node

const debugPort = Number.parseInt(process.argv[2] ?? '9229', 10)
const timeoutMs = Number.parseInt(process.argv[3] ?? '480000', 10)

const targets = await fetch(`http://127.0.0.1:${debugPort}/json/list`).then((response) =>
  response.json(),
)
const target = targets.find(
  (candidate) => candidate.type === 'page' && candidate.url.startsWith('http://127.0.0.1:'),
)
if (!target?.webSocketDebuggerUrl) {
  throw new Error('No loopback WFMHub page was found in the Chrome debugging targets')
}

const socket = new WebSocket(target.webSocketDebuggerUrl)
await new Promise((resolve, reject) => {
  socket.addEventListener('open', resolve, { once: true })
  socket.addEventListener('error', reject, { once: true })
})

let nextId = 1
const pending = new Map()
socket.addEventListener('message', (event) => {
  const message = JSON.parse(event.data)
  if (message.id && pending.has(message.id)) {
    const { resolve, reject } = pending.get(message.id)
    pending.delete(message.id)
    if (message.error) reject(new Error(message.error.message))
    else resolve(message.result)
  }
})

function command(method, params = {}) {
  const id = nextId++
  return new Promise((resolve, reject) => {
    pending.set(id, { resolve, reject })
    socket.send(JSON.stringify({ id, method, params }))
  })
}

async function evaluate(expression) {
  const result = await command('Runtime.evaluate', {
    expression,
    awaitPromise: true,
    returnByValue: true,
  })
  if (result.exceptionDetails) {
    throw new Error(result.exceptionDetails.text ?? 'Chrome evaluation failed')
  }
  return result.result.value
}

await command('Runtime.enable')
const doctorDeadline = Date.now() + 30_000
let openedDoctor = false
while (Date.now() < doctorDeadline && !openedDoctor) {
  openedDoctor = await evaluate(`(() => {
    if (location.pathname === '/compatibility') return true;
    const link = [...document.querySelectorAll('a')]
      .find((candidate) => candidate.getAttribute('href') === '/compatibility');
    if (!link || location.hash.includes('wfmhub_token')) return false;
    link.click();
    return true;
  })()`)
  if (!openedDoctor) await new Promise((resolve) => setTimeout(resolve, 250))
}
if (!openedDoctor) throw new Error('Compatibility doctor link was not available')

const readinessDeadline = Date.now() + 60_000
let clicked = false
while (Date.now() < readinessDeadline && !clicked) {
  clicked = await evaluate(`(() => {
    const button = [...document.querySelectorAll('button')]
      .find((candidate) => candidate.textContent?.includes('Run all probes'));
    if (!button || button.disabled) return false;
    button.click();
    return true;
  })()`)
  if (!clicked) await new Promise((resolve) => setTimeout(resolve, 250))
}
if (!clicked) throw new Error('Run all probes button was not available')

const deadline = Date.now() + timeoutMs
let body = ''
while (Date.now() < deadline) {
  body = await evaluate('document.body.innerText')
  if (
    body.includes('Hybrid browser stack passed this machine') ||
    body.includes('One or more browser capabilities are unavailable')
  ) {
    break
  }
  await new Promise((resolve) => setTimeout(resolve, 1000))
}

socket.close()
if (!body.includes('Hybrid browser stack passed this machine')) {
  console.error(body)
  throw new Error('Hybrid browser compatibility smoke did not pass every probe')
}
console.log('Hybrid browser compatibility smoke passed every probe.')
