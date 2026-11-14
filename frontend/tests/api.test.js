import test from 'node:test';
import assert from 'node:assert/strict';
import {apiJson} from '../src/api.js';

test('SPA HTML fallback gives an actionable connection error, not a JSON SyntaxError', async () => {
  const response=new Response('<!doctype html><html>Frontend</html>',{headers:{'Content-Type':'text/html'}});
  await assert.rejects(apiJson(response), /Restart the frontend development server/);
});
test('valid API JSON and structured API errors remain readable', async () => {
  for (const body of [{routing_available:true},{code:'dataset_mismatch',message:'Reload data'}]) {
    const response=new Response(JSON.stringify(body),{headers:{'Content-Type':'application/json; charset=utf-8'}});
    assert.deepEqual(await apiJson(response),body);
  }
});
test('malformed API JSON is reported as unreadable data', async () => {
  const response=new Response('broken',{headers:{'Content-Type':'application/json'}});
  await assert.rejects(apiJson(response), /unreadable data/);
});
