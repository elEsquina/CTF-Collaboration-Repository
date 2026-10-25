import {useEffect,useState} from 'react';
import {BrowserRouter,Routes,Route,Link,NavLink,Navigate,useNavigate} from 'react-router-dom';
import {Terminal,LayoutGrid,Plus,LogOut} from 'lucide-react';
import {api,setCsrf} from './services/api';
import {Loading,ErrorMessage} from './components/UI';
import Login from './pages/Login';
import Dashboard from './pages/Dashboard';
import SubmitChallenge from './pages/SubmitChallenge';
import ChallengeDetails from './pages/ChallengeDetails';
import EditChallenge from './pages/EditChallenge';
function Application() {
 const [loggedIn,setLoggedIn]=useState(null),[error,setError]=useState(''),navigate=useNavigate();
 useEffect(()=>{api('/me').then(({data})=>{setCsrf(data.csrf_token);setLoggedIn(true);}).catch(()=>setLoggedIn(false));const expired=()=>{setCsrf('');setLoggedIn(false);};window.addEventListener('session-expired',expired);return()=>window.removeEventListener('session-expired',expired);},[]);
 async function logout(){try{await api('/logout',{method:'POST'});setCsrf('');setLoggedIn(false);navigate('/login');}catch(e){setError(e.message);}}
 if(loggedIn===null)return <Loading/>;
 if(!loggedIn)return <Routes><Route path="/login" element={<Login onLogin={()=>{setLoggedIn(true);navigate('/');}}/>}/><Route path="*" element={<Navigate to="/login" replace/>}/></Routes>;
 return <div className="app"><header><div className="header-inner"><Link className="brand" to="/"><div className="brand-icon"><Terminal size={22}/></div><span className="brand-name">ACM CTF Track Challenge Tool</span></Link><nav><NavLink to="/" end aria-label="Repository"><LayoutGrid size={16}/><span>Repository</span></NavLink><NavLink to="/submit" aria-label="Submit challenge"><Plus size={16}/><span>Submit challenge</span></NavLink></nav><button className="logout" onClick={logout} aria-label="Log out"><LogOut size={16}/><span>Log out</span></button></div></header><main className="main"><ErrorMessage message={error}/><Routes><Route path="/" element={<Dashboard/>}/><Route path="/submit" element={<SubmitChallenge/>}/><Route path="/challenges/:id" element={<ChallengeDetails/>}/><Route path="/challenges/:id/edit" element={<EditChallenge/>}/><Route path="/login" element={<Navigate to="/" replace/>}/><Route path="*" element={<div className="empty"><h1>Page not found.</h1><Link className="button primary" to="/">Return to repository</Link></div>}/></Routes></main></div>;
}
export default function App(){return <BrowserRouter><Application/></BrowserRouter>;}
