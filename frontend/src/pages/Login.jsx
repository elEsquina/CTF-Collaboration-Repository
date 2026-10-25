import {useState} from 'react';
import {ArrowRight, LockKeyhole, Eye, EyeOff} from 'lucide-react';
import {api,setCsrf} from '../services/api';
import {ErrorMessage} from '../components/UI';
export default function Login({onLogin}) {
 const [password,setPassword]=useState(''),[error,setError]=useState(''),[busy,setBusy]=useState(false),[visible,setVisible]=useState(false);
 async function submit(e) {e.preventDefault();setBusy(true);setError('');try {const {data}=await api('/login',{method:'POST',body:JSON.stringify({password})});setCsrf(data.csrf_token);onLogin();}catch(e){setError(e.message);}finally{setBusy(false);}}
 return <main className="login-screen"><div className="login-panel"><h1>ACM CTF Track Challenge Tool</h1><form onSubmit={submit}><ErrorMessage message={error}/><label htmlFor="password">Shared password</label><div className="secret-input"><LockKeyhole size={18} className="input-leading"/><input id="password" className="with-leading" type={visible?'text':'password'} autoComplete="current-password" value={password} onChange={e=>setPassword(e.target.value)} placeholder="Enter your team's password" required autoFocus/><button type="button" className="icon-button" aria-label={visible?'Hide password':'Show password'} onClick={()=>setVisible(!visible)}>{visible?<EyeOff size={18}/>:<Eye size={18}/>}</button></div><button className="button primary login-button" disabled={busy}>{busy?'Signing in…':'Log in'}<ArrowRight size={18}/></button></form></div></main>;
}
