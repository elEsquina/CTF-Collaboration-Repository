import {afterEach, test} from 'node:test';
import assert from 'node:assert/strict';
import {api,setCsrf} from '../src/services/api.js';
const originalFetch = globalThis.fetch;
afterEach(()=>{ globalThis.fetch=originalFetch; setCsrf(''); delete globalThis.window; });

test('JSON writes send same-origin credentials and the current CSRF token', async()=>{
 setCsrf('session-token');
 globalThis.fetch=async(url,options)=>{
  assert.equal(url,'/api/challenges/1');
  assert.equal(options.credentials,'same-origin');
  assert.equal(options.headers['X-CSRF-Token'],'session-token');
  assert.equal(options.headers['Content-Type'],'application/json');
  return Response.json({data:{id:1}});
 };
 assert.deepEqual(await api('/challenges/1',{method:'PATCH',body:'{}'}),{data:{id:1}});
});

test('multipart writes let the browser generate its boundary',async()=>{
 const form=new FormData(); form.append('name','Example');
 globalThis.fetch=async(url,options)=>{
  assert.equal(options.body,form);
  assert.equal(options.headers['Content-Type'],undefined);
  return Response.json({data:{id:2}});
 };
 await api('/challenges',{method:'POST',body:form});
});

test('API validation messages reach the form unchanged',async()=>{
 globalThis.fetch=async()=>Response.json({error:{message:'ZIP contains an unsafe path.'}},{status:422});
 await assert.rejects(api('/challenges'),{message:'ZIP contains an unsafe path.'});
});

test('expired sessions notify the application',async()=>{
 let event;
 globalThis.window={dispatchEvent:value=>{event=value;}};
 globalThis.fetch=async()=>Response.json({error:{message:'Please log in.'}},{status:401});
 await assert.rejects(api('/me'),{message:'Please log in.'});
 assert.equal(event.type,'session-expired');
});

test('wrong login password does not dispatch a session-expired event',async()=>{
 globalThis.window={dispatchEvent:()=>assert.fail('Unexpected session event')};
 globalThis.fetch=async()=>Response.json({error:{message:'Incorrect password.'}},{status:401});
 await assert.rejects(api('/login',{method:'POST',body:'{}'}),{message:'Incorrect password.'});
});

test('network failures show a useful connection message',async()=>{
 globalThis.fetch=async()=>{throw new TypeError('fetch failed');};
 await assert.rejects(api('/challenges'),{message:'Unable to reach the server. Please try again.'});
});

test('non-JSON proxy errors show a useful message',async()=>{
 globalThis.fetch=async()=>new Response('<html>Bad gateway</html>',{status:502});
 await assert.rejects(api('/challenges'),{message:'The server returned an unexpected response. Please try again.'});
});
